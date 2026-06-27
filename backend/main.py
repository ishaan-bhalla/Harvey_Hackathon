import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from services.report_generator import run_analysis
from services.document_parser import parse_document
import uuid

app = FastAPI(title="Pleading-to-Proof API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# In-memory stores
_documents_cache = None
_jobs = {}  # job_id -> {status, result, error}
_reviews = []

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
    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)

# Background pleading analysis task
def run_pleading_job(job_id: str, primary_pdf: str, comparison_pdfs: list[str]):
    try:
        from services.pleading_generator import run_pleading_analysis_with_progress
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["progress"] = 5
        _jobs[job_id]["progress_message"] = "Parsing documents..."

        all_docs = [primary_pdf] + comparison_pdfs

        def progress_callback(current: int, total: int, message: str):
            _jobs[job_id]["progress"] = int((current / total) * 90) + 5
            _jobs[job_id]["progress_message"] = message

        result = run_pleading_analysis_with_progress(all_docs, progress_callback)
        _jobs[job_id]["status"] = "complete"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["progress_message"] = "Complete"
        _jobs[job_id]["result"] = result
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
    return {"status": "recorded", "total_reviews": len(_reviews)}

@app.get("/reviews/{job_id}")
def get_reviews(job_id: str):
    job_reviews = [r for r in _reviews if r["job_id"] == job_id]
    return {"job_id": job_id, "reviews": job_reviews, "count": len(job_reviews)}

@app.get("/graph")
def get_graph():
    """Returns witness-allegation relationship graph for visualisation."""
    try:
        from clients.neo4j_client import get_graph_data
        return get_graph_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
