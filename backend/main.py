import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from services.report_generator import run_analysis
from services.document_parser import parse_document
from services.storage import (
    save_job, load_jobs, save_reviews, load_reviews,
    save_demo, load_demo, save_snapshot, load_snapshots
)
import uuid

app = FastAPI(title="Pleading-to-Proof API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Persistent stores — survive server restarts
_documents_cache = None
_jobs = load_jobs()
_reviews = load_reviews()
_demo_result = load_demo()

# Request schemas
class AnalysisRequest(BaseModel):
    primary_pdf: str
    comparison_pdfs: list[str]

class ReviewRequest(BaseModel):
    job_id: str
    allegation_id: int
    ai_verdict: str
    decision: str          # "accepted", "overruled", "rejected"
    reviewer_note: str = ""

class SnapshotRequest(BaseModel):
    label: str
    job_id: str

# Health check
@app.get("/health")
def health():
    return {"status": "ok"}

# Documents list with caching
@app.get("/documents")
def list_documents():
    global _documents_cache
    if _documents_cache is not None:
        return _documents_cache

    data_dir = "data/raw"
    files = sorted([f for f in os.listdir(data_dir) if f.lower().endswith(".pdf")])

    structured = []
    for filename in files:
        filepath = os.path.join(data_dir, filename)
        try:
            doc = parse_document(filepath)
            witness_name = doc.witness_name
            statement_id = doc.statement_number
        except Exception:
            witness_name = "Unknown"
            statement_id = filename.replace(".pdf", "")

        structured.append({
            "filename": filename,
            "witness_name": witness_name,
            "statement_id": statement_id
        })

    _documents_cache = {"documents": structured, "count": len(structured)}
    return _documents_cache

# Background analysis task
def run_analysis_job(job_id: str, primary_pdf: str, comparison_pdfs: list[str]):
    try:
        _jobs[job_id]["status"] = "running"
        save_job(job_id, _jobs[job_id])
        report = run_analysis(primary_pdf, comparison_pdfs)
        _jobs[job_id]["status"] = "complete"
        _jobs[job_id]["result"] = {
            "primary_witness": report.primary_witness,
            "comparison_witnesses": report.comparison_witnesses,
            "total_claims": report.total_claims,
            "trial_readiness": report.trial_readiness,
            "trial_readiness_score": report.trial_readiness_score,
            "matrix": [
                {
                    "allegation_summary": row.allegation_summary,
                    "allegation_type": row.allegation_type,
                    "topic": row.topic,
                    "paragraph_ref": row.paragraph_ref,
                    "witness_a": row.witness_a,
                    "supporting": row.supporting,
                    "contradicting": row.contradicting,
                    "neutral": row.neutral,
                    "not_addressed": row.not_addressed,
                    "gap": row.gap,
                    "confidence": row.confidence
                }
                for row in report.matrix
            ],
            "gaps_count": len(report.gaps),
            "contradictions_count": len(report.contradictions),
            "gaps": [
                {
                    "allegation_summary": row.allegation_summary,
                    "topic": row.topic,
                    "paragraph_ref": row.paragraph_ref
                }
                for row in report.gaps
            ],
            "contradictions": [
                {
                    "allegation_summary": row.allegation_summary,
                    "topic": row.topic,
                    "contradicting": row.contradicting
                }
                for row in report.contradictions
            ]
        }
        save_job(job_id, _jobs[job_id])
    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
        save_job(job_id, _jobs[job_id])

# Background pleading analysis task
def run_pleading_job(job_id: str, primary_pdf: str, comparison_pdfs: list[str]):
    try:
        from services.pleading_generator import run_pleading_analysis_with_progress
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["progress"] = 5
        _jobs[job_id]["progress_message"] = "Parsing documents..."
        save_job(job_id, _jobs[job_id])

        all_docs = [primary_pdf] + comparison_pdfs

        def progress_callback(current: int, total: int, message: str):
            _jobs[job_id]["progress"] = int((current / total) * 90) + 5
            _jobs[job_id]["progress_message"] = message

        result = run_pleading_analysis_with_progress(all_docs, progress_callback)
        _jobs[job_id]["status"] = "complete"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["progress_message"] = "Complete"
        _jobs[job_id]["result"] = result
        save_job(job_id, _jobs[job_id])
        # Build Neo4j graph from results
        try:
            from clients.neo4j_client import build_graph_from_analysis
            build_graph_from_analysis(result)
            print("Neo4j graph updated")
        except Exception as e:
            print(f"Neo4j graph update failed (non-critical): {e}")
    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["progress"] = 0
        _jobs[job_id]["progress_message"] = f"Failed: {str(e)}"
        _jobs[job_id]["error"] = str(e)
        save_job(job_id, _jobs[job_id])

# Submit analysis job — returns immediately with job_id
@app.post("/analyze")
def analyze(request: AnalysisRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "queued", "result": None, "error": None, "progress": 0, "progress_message": "Queued"}
    background_tasks.add_task(
        run_analysis_job,
        job_id,
        request.primary_pdf,
        request.comparison_pdfs
    )
    return {"job_id": job_id, "status": "queued"}

@app.post("/analyze/pleading")
def analyze_pleading(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """
    Runs the synthetic pleading analysis — tests 8 formal Horizon allegations
    against the selected witness statements. More powerful than witness-vs-witness.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "queued", "result": None, "error": None, "progress": 0, "progress_message": "Queued"}
    background_tasks.add_task(
        run_pleading_job,
        job_id,
        request.primary_pdf,
        request.comparison_pdfs
    )
    return {"job_id": job_id, "status": "queued"}

@app.post("/review")
def submit_review(request: ReviewRequest):
    from datetime import datetime
    _reviews.append({
        "job_id": request.job_id,
        "allegation_id": request.allegation_id,
        "ai_verdict": request.ai_verdict,
        "lawyer_decision": request.decision,
        "reviewer_note": request.reviewer_note,
        "timestamp": datetime.now().isoformat()
    })
    save_reviews(_reviews)
    return {"status": "recorded", "total_reviews": len(_reviews)}

@app.get("/reviews/{job_id}")
def get_reviews(job_id: str):
    job_reviews = [r for r in _reviews if r["job_id"] == job_id]
    return {"job_id": job_id, "reviews": job_reviews, "count": len(job_reviews)}

@app.post("/snapshots")
def create_snapshot(request: SnapshotRequest):
    if request.job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = _jobs[request.job_id]
    if job["status"] != "complete":
        raise HTTPException(status_code=400, detail="Job not complete yet")
    snapshot = save_snapshot(request.label, job["result"])
    return {
        "status": "saved",
        "snapshot_id": snapshot["id"],
        "label": snapshot["label"],
        "timestamp": snapshot["timestamp"],
        "trial_readiness": snapshot["trial_readiness"],
        "trial_readiness_score": snapshot["trial_readiness_score"]
    }

@app.get("/snapshots")
def list_snapshots():
    snapshots = load_snapshots()
    return {
        "snapshots": [
            {
                "id": s["id"],
                "label": s["label"],
                "timestamp": s["timestamp"],
                "trial_readiness": s["trial_readiness"],
                "trial_readiness_score": s["trial_readiness_score"],
                "gaps_count": s["gaps_count"],
                "contradictions_count": s["contradictions_count"],
                "documents_analysed": s["documents_analysed"]
            }
            for s in snapshots
        ],
        "count": len(snapshots)
    }

@app.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: int):
    snapshots = load_snapshots()
    for s in snapshots:
        if s["id"] == snapshot_id:
            return s
    raise HTTPException(status_code=404, detail="Snapshot not found")

@app.get("/graph")
def get_graph():
    """Returns witness-allegation relationship graph for visualisation."""
    try:
        from clients.neo4j_client import get_graph_data
        return get_graph_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/demo")
def get_demo():
    """
    Returns pre-computed analysis result instantly.
    Use this for presentations — no waiting for Claude API.
    """
    global _demo_result
    if _demo_result is None:
        raise HTTPException(
            status_code=404,
            detail="Demo not pre-computed yet. POST to /demo/precompute first."
        )
    return _demo_result

@app.post("/demo/precompute")
def precompute_demo(background_tasks: BackgroundTasks):
    """
    Runs the best witness combination and caches the result.
    Call this once before the presentation.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "queued", "result": None, "error": None, "progress": 0, "progress_message": "Queued"}
    background_tasks.add_task(
        run_demo_precompute,
        job_id
    )
    return {"job_id": job_id, "status": "queued", "message": "Pre-computing demo result..."}

def run_demo_precompute(job_id: str):
    global _demo_result
    try:
        from services.pleading_generator import run_pleading_analysis_with_progress
        _jobs[job_id]["status"] = "running"
        save_job(job_id, _jobs[job_id])

        # Best witness combination — produces STRONG 75% with 2 contradictions
        all_docs = [
            "data/raw/WITN03540100.pdf",
            "data/raw/witn04510100.pdf",
            "data/raw/WITN04770100 - Steve Bansal - Witness statement.pdf",
            "data/raw/witn09830100.pdf",
            "data/raw/WITN08130100.pdf",
            "data/raw/WITN04630100 - Rod Ismay - First Witness Statement.pdf"
        ]

        def progress_callback(current, total, message):
            _jobs[job_id]["progress"] = int((current / total) * 90) + 5
            _jobs[job_id]["progress_message"] = message

        result = run_pleading_analysis_with_progress(all_docs, progress_callback)

        # Cache it
        _demo_result = result
        save_demo(result)

        # Also build Neo4j graph
        try:
            from clients.neo4j_client import build_graph_from_analysis
            build_graph_from_analysis(result)
        except Exception as e:
            print(f"Neo4j update failed: {e}")

        _jobs[job_id]["status"] = "complete"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["progress_message"] = "Demo pre-computed and cached"
        _jobs[job_id]["result"] = result
        save_job(job_id, _jobs[job_id])
        print("Demo result cached successfully")

    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
        save_job(job_id, _jobs[job_id])
        print(f"Demo precompute failed: {e}")

# Poll for job status
@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = _jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job.get("progress", 0),
        "progress_message": job.get("progress_message", ""),
        "result": job["result"],
        "error": job["error"]
    }
