import json
from clients.claude_client import call_claude
from dataclasses import dataclass

@dataclass
class Classification:
    allegation_id: int
    allegation_summary: str
    witness_a: str
    witness_b: str
    statement_b: str
    verdict: str
    confidence: str
    relevant_passage: str
    paragraph_ref: str
    reasoning: str

def load_prompt() -> str:
    with open("backend/prompts/classify_evidence.txt", "r") as f:
        return f.read()

def classify_against_witness(allegation, document_b) -> Classification:
    """
    Given one allegation from witness A, check what witness B says about it.
    """
    prompt_template = load_prompt()

    # Limit evidence doc to 6000 chars to leave room for the allegation
    evidence_text = document_b.raw_text[:6000]

    prompt = f"""
{prompt_template}

CLAIM TO EVALUATE:
Witness: {allegation.witness_name}
Claim type: {allegation.type}
Claim: {allegation.summary}
Topic: {allegation.topic}

SECOND WITNESS STATEMENT TO SEARCH:
Witness: {document_b.witness_name}
Statement: {document_b.statement_number}

{evidence_text}
"""

    response = call_claude(
        prompt=prompt,
        system="You are a precise legal analyst. Always return valid JSON only.",
        max_tokens=1000
    )

    try:
        raw = json.loads(response)
    except json.JSONDecodeError:
        cleaned = response.strip().strip("```json").strip("```").strip()
        raw = json.loads(cleaned)

    return Classification(
        allegation_id=allegation.id,
        allegation_summary=allegation.summary,
        witness_a=allegation.witness_name,
        witness_b=document_b.witness_name,
        statement_b=document_b.statement_number,
        verdict=raw.get("verdict", "NOT_ADDRESSED"),
        confidence=raw.get("confidence", "LOW"),
        relevant_passage=raw.get("relevant_passage", None),
        paragraph_ref=raw.get("paragraph_ref", None),
        reasoning=raw.get("reasoning", "")
    )
