import json
import os
from datetime import datetime

STORAGE_DIR = "storage"
JOBS_FILE = f"{STORAGE_DIR}/jobs.json"
REVIEWS_FILE = f"{STORAGE_DIR}/reviews.json"
SNAPSHOTS_FILE = f"{STORAGE_DIR}/snapshots.json"
DEMO_FILE = f"{STORAGE_DIR}/demo_result.json"

def ensure_storage():
    os.makedirs(STORAGE_DIR, exist_ok=True)
    for f in [JOBS_FILE, REVIEWS_FILE, SNAPSHOTS_FILE]:
        if not os.path.exists(f):
            with open(f, "w") as file:
                json.dump({} if "jobs" in f else [], file)

def save_job(job_id: str, job: dict):
    ensure_storage()
    try:
        with open(JOBS_FILE, "r") as f:
            jobs = json.load(f)
        jobs[job_id] = job
        with open(JOBS_FILE, "w") as f:
            json.dump(jobs, f)
    except Exception as e:
        print(f"Storage error saving job: {e}")

def load_jobs() -> dict:
    ensure_storage()
    try:
        with open(JOBS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_reviews(reviews: list):
    ensure_storage()
    try:
        with open(REVIEWS_FILE, "w") as f:
            json.dump(reviews, f)
    except Exception as e:
        print(f"Storage error saving reviews: {e}")

def load_reviews() -> list:
    ensure_storage()
    try:
        with open(REVIEWS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_demo(result: dict):
    ensure_storage()
    try:
        with open(DEMO_FILE, "w") as f:
            json.dump(result, f)
    except Exception as e:
        print(f"Storage error saving demo: {e}")

def load_demo() -> dict:
    ensure_storage()
    try:
        if os.path.exists(DEMO_FILE):
            with open(DEMO_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return None

def save_snapshot(label: str, result: dict) -> dict:
    ensure_storage()
    try:
        with open(SNAPSHOTS_FILE, "r") as f:
            snapshots = json.load(f)
    except Exception:
        snapshots = []

    snapshot = {
        "id": len(snapshots) + 1,
        "label": label,
        "timestamp": datetime.now().isoformat(),
        "trial_readiness": result.get("trial_readiness"),
        "trial_readiness_score": result.get("trial_readiness_score"),
        "total_allegations": result.get("total_allegations"),
        "gaps_count": len(result.get("gaps", [])),
        "contradictions_count": len(result.get("contradictions", [])),
        "documents_analysed": result.get("documents_analysed", []),
        "result": result
    }
    snapshots.append(snapshot)

    with open(SNAPSHOTS_FILE, "w") as f:
        json.dump(snapshots, f)

    return snapshot

def load_snapshots() -> list:
    ensure_storage()
    try:
        with open(SNAPSHOTS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []
