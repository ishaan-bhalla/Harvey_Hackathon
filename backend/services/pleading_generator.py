import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from clients.claude_client import call_claude
import json

def verify_quote(quote: str, raw_text: str) -> bool:
    """
    String-match the quote back into the source document.
    If we can't find it verbatim, the citation is unverified.
    """
    if not quote:
        return False
    # Normalise whitespace for matching
    normalised_quote = " ".join(quote.split()).lower()
    normalised_text = " ".join(raw_text.split()).lower()
    return normalised_quote in normalised_text

HORIZON_PLEADINGS = [
    {
        "id": 1,
        "allegation": "The Horizon IT system contained bugs, errors and defects that caused false shortfalls in subpostmasters' branch accounts.",
        "topic": "horizon_system",
        "party": "Post Office / Fujitsu"
    },
    {
        "id": 2,
        "allegation": "Post Office Limited knew or ought to have known about defects in the Horizon system before and during the prosecution of subpostmasters.",
        "topic": "knowledge",
        "party": "Post Office"
    },
    {
        "id": 3,
        "allegation": "Fujitsu had the ability to remotely access and alter transaction data in branch accounts without subpostmasters' knowledge or consent.",
        "topic": "horizon_system",
        "party": "Fujitsu"
    },
    {
        "id": 4,
        "allegation": "Post Office Limited failed to disclose known Horizon defects to subpostmasters and their legal representatives during criminal proceedings.",
        "topic": "prosecutions",
        "party": "Post Office"
    },
    {
        "id": 5,
        "allegation": "Subpostmasters were wrongly prosecuted for false accounting and theft as a result of Horizon-generated shortfalls.",
        "topic": "prosecutions",
        "party": "Post Office"
    },
    {
        "id": 6,
        "allegation": "Post Office Limited's senior management were aware that Horizon was not reliable but continued to use its data as the basis for prosecutions.",
        "topic": "management",
        "party": "Post Office"
    },
    {
        "id": 7,
        "allegation": "The Known Error Log maintained by Fujitsu recorded system defects that were not shared with subpostmasters or their lawyers.",
        "topic": "knowledge",
        "party": "Fujitsu"
    },
    {
        "id": 8,
        "allegation": "Post Office Limited applied pressure on subpostmasters to make good shortfalls from their personal funds despite the shortfalls being caused by Horizon errors.",
        "topic": "financial_losses",
        "party": "Post Office"
    }
]

def classify_witness_against_pleading(allegation: dict, document) -> dict:
    """
    Search through the entire document in chunks to find
    relevant passages, then classify.
    """
    import re
    from utils.text_chunker import find_relevant_chunks

    topic_keywords = {
        "horizon_system": ["horizon", "bug", "error", "defect", "shortfall", "remote", "access", "integrity"],
        "knowledge": ["knew", "aware", "knowledge", "known error", "KEL", "reported", "informed"],
        "prosecutions": ["prosecut", "criminal", "disclosure", "defence", "convicted", "charges"],
        "management": ["management", "senior", "director", "decision", "policy", "board"],
        "financial_losses": ["shortfall", "debt", "repay", "losses", "financial", "pressure", "make good"]
    }

    keywords = topic_keywords.get(allegation["topic"], [])
    relevant_text = find_relevant_chunks(document.raw_text, keywords)

    prompt = f"""You are a litigation analyst for the Post Office Horizon IT Inquiry.

Given this formal allegation and relevant excerpts from a witness statement, determine whether the witness SUPPORTS, CONTRADICTS, or does NOT ADDRESS the allegation.

FORMAL ALLEGATION:
"{allegation['allegation']}"
Topic: {allegation['topic']}

RELEVANT EXCERPTS FROM {document.witness_name.upper()}'S STATEMENT:
{relevant_text[:5000]}

Return ONLY valid JSON:
{{
  "verdict": "SUPPORTS" | "CONTRADICTS" | "NOT_ADDRESSED",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "relevant_passage": "exact short quote from the excerpts (null if NOT_ADDRESSED)",
  "paragraph_ref": "paragraph number or null",
  "reasoning": "one sentence explanation"
}}"""

    response = call_claude(
        prompt=prompt,
        system="You are a precise legal analyst. Return valid JSON only.",
        max_tokens=800
    )

    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', response, re.DOTALL)
        result = json.loads(match.group()) if match else {
            "verdict": "NOT_ADDRESSED",
            "confidence": "LOW",
            "relevant_passage": None,
            "paragraph_ref": None,
            "reasoning": "Could not parse response"
        }

    # Verify the quote actually exists in the document
    passage = result.get("relevant_passage")
    if passage and not verify_quote(passage, document.raw_text):
        result["relevant_passage"] = None
        result["verified"] = False
        result["confidence"] = "LOW"
        if result["verdict"] in ["SUPPORTS", "CONTRADICTS"]:
            result["verdict"] = "UNVERIFIED"
    else:
        result["verified"] = True

    return {
        "allegation_id": allegation["id"],
        "allegation": allegation["allegation"],
        "topic": allegation["topic"],
        "witness": document.witness_name,
        "statement_id": document.statement_number,
        "verified": result.get("verified", True),
        **result
    }

def run_pleading_analysis(document_paths: list) -> dict:
    from services.document_parser import parse_document

    print(f"Parsing {len(document_paths)} documents...")
    documents = []
    for path in document_paths:
        try:
            doc = parse_document(path)
            documents.append(doc)
            print(f"  Parsed: {doc.witness_name}")
        except Exception as e:
            print(f"  Failed: {path} — {e}")

    matrix = []

    for allegation in HORIZON_PLEADINGS:
        print(f"\nAllegation {allegation['id']}: {allegation['allegation'][:60]}...")
        row = {
            "allegation_id": allegation["id"],
            "allegation": allegation["allegation"],
            "topic": allegation["topic"],
            "supporting": [],
            "contradicting": [],
            "not_addressed": [],
            "gap": True
        }

        for doc in documents:
            result = classify_witness_against_pleading(allegation, doc)
            print(f"  {doc.witness_name}: {result['verdict']} ({result['confidence']})")

            if result["verdict"] == "SUPPORTS":
                row["supporting"].append(result)
                row["gap"] = False
            elif result["verdict"] == "CONTRADICTS":
                row["contradicting"].append(result)
                row["gap"] = False
            else:
                row["not_addressed"].append(doc.witness_name)

        matrix.append(row)

    supported = sum(1 for r in matrix if len(r["supporting"]) > 0)
    score = round((supported / len(matrix)) * 100, 1)

    if score >= 70:
        readiness = "STRONG"
    elif score >= 40:
        readiness = "MODERATE"
    else:
        readiness = "VULNERABLE"

    return {
        "documents_analysed": [d.witness_name for d in documents],
        "total_allegations": len(HORIZON_PLEADINGS),
        "trial_readiness": readiness,
        "trial_readiness_score": score,
        "matrix": matrix,
        "gaps": [r for r in matrix if r["gap"]],
        "contradictions": [r for r in matrix if len(r["contradicting"]) > 0]
    }

def run_pleading_analysis_with_progress(document_paths: list, progress_callback=None) -> dict:
    """
    Same as run_pleading_analysis but calls progress_callback
    after each allegation is processed so the frontend can show a progress bar.
    """
    from services.document_parser import parse_document

    print(f"Parsing {len(document_paths)} documents...")
    documents = []
    for path in document_paths:
        try:
            doc = parse_document(path)
            documents.append(doc)
            print(f"  Parsed: {doc.witness_name}")
        except Exception as e:
            print(f"  Failed: {path} — {e}")

    total_steps = len(HORIZON_PLEADINGS)
    matrix = []

    for i, allegation in enumerate(HORIZON_PLEADINGS):
        if progress_callback:
            progress_callback(
                i,
                total_steps,
                f"Analysing allegation {i+1}/{total_steps}: {allegation['topic'].replace('_', ' ')}"
            )

        print(f"\nAllegation {allegation['id']}: {allegation['allegation'][:60]}...")
        row = {
            "allegation_id": allegation["id"],
            "allegation": allegation["allegation"],
            "topic": allegation["topic"],
            "supporting": [],
            "contradicting": [],
            "not_addressed": [],
            "gap": True
        }

        for doc in documents:
            result = classify_witness_against_pleading(allegation, doc)
            print(f"  {doc.witness_name}: {result['verdict']} ({result['confidence']})")

            if result["verdict"] == "SUPPORTS":
                row["supporting"].append(result)
                row["gap"] = False
            elif result["verdict"] == "CONTRADICTS":
                row["contradicting"].append(result)
                row["gap"] = False
            elif result["verdict"] == "UNVERIFIED":
                row["not_addressed"].append(doc.witness_name)
            else:
                row["not_addressed"].append(doc.witness_name)

        matrix.append(row)

    if progress_callback:
        progress_callback(total_steps, total_steps, "Generating report...")

    supported = sum(1 for r in matrix if len(r["supporting"]) > 0)
    score = round((supported / len(matrix)) * 100, 1)

    if score >= 70:
        readiness = "STRONG"
    elif score >= 40:
        readiness = "MODERATE"
    else:
        readiness = "VULNERABLE"

    return {
        "documents_analysed": [d.witness_name for d in documents],
        "total_allegations": len(HORIZON_PLEADINGS),
        "trial_readiness": readiness,
        "trial_readiness_score": score,
        "matrix": matrix,
        "gaps": [r for r in matrix if r["gap"]],
        "contradictions": [r for r in matrix if len(r["contradicting"]) > 0]
    }
