import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def detect_changes(old_result: dict, new_result: dict) -> dict:
    """
    Compares two analysis results and returns what changed.
    Used when new evidence is added to an existing case.
    """
    changes = []
    old_matrix = {row["allegation_id"]: row for row in old_result.get("matrix", [])}
    new_matrix = {row["allegation_id"]: row for row in new_result.get("matrix", [])}

    for allegation_id, new_row in new_matrix.items():
        old_row = old_matrix.get(allegation_id)
        if not old_row:
            continue

        old_supported = len(old_row["supporting"]) > 0
        new_supported = len(new_row["supporting"]) > 0
        old_contradicted = len(old_row["contradicting"]) > 0
        new_contradicted = len(new_row["contradicting"]) > 0
        old_gap = old_row["gap"]
        new_gap = new_row["gap"]

        # Detect status change
        old_status = "SUPPORTED" if old_supported else "CONTRADICTED" if old_contradicted else "GAP"
        new_status = "SUPPORTED" if new_supported else "CONTRADICTED" if new_contradicted else "GAP"

        if old_status != new_status:
            changes.append({
                "allegation_id": allegation_id,
                "allegation": new_row["allegation"],
                "topic": new_row["topic"],
                "old_status": old_status,
                "new_status": new_status,
                "change_type": "STRENGTHENED" if new_status == "SUPPORTED" else "WEAKENED" if new_status == "GAP" else "CONTRADICTED",
                "new_witnesses": [
                    s["witness"] for s in new_row["supporting"]
                    if s["witness"] not in [o["witness"] for o in old_row["supporting"]]
                ]
            })

    # Score change
    old_score = old_result.get("trial_readiness_score", 0)
    new_score = new_result.get("trial_readiness_score", 0)
    score_delta = round(new_score - old_score, 1)

    return {
        "allegation_changes": changes,
        "score_before": old_score,
        "score_after": new_score,
        "score_delta": score_delta,
        "readiness_before": old_result.get("trial_readiness"),
        "readiness_after": new_result.get("trial_readiness"),
        "new_documents": [
            d for d in new_result.get("documents_analysed", [])
            if d not in old_result.get("documents_analysed", [])
        ],
        "summary": f"Score changed from {old_score}% to {new_score}% ({'+' if score_delta >= 0 else ''}{score_delta}%). {len(changes)} allegation(s) changed status."
    }
