import json
import sys
sys.path.insert(0, 'backend')

from services.document_parser import parse_document
from services.allegation_extractor import extract_allegations
from services.evidence_classifier import classify_against_witness
from dataclasses import dataclass, asdict

@dataclass
class MatrixRow:
    allegation_summary: str
    allegation_type: str
    topic: str
    paragraph_ref: str
    witness_a: str
    supporting: list
    contradicting: list
    neutral: list
    not_addressed: int
    gap: bool
    confidence: str

@dataclass
class AnalysisReport:
    primary_witness: str
    comparison_witnesses: list
    total_claims: int
    matrix: list
    trial_readiness: str
    trial_readiness_score: float
    gaps: list
    contradictions: list

def calculate_trial_readiness(matrix: list) -> tuple:
    if not matrix:
        return "UNKNOWN", 0.0

    supported = sum(1 for row in matrix if len(row.supporting) > 0)
    score = supported / len(matrix)

    if score >= 0.7:
        label = "STRONG"
    elif score >= 0.4:
        label = "MODERATE"
    else:
        label = "VULNERABLE"

    return label, round(score * 100, 1)

def run_analysis(primary_pdf: str, comparison_pdfs: list) -> AnalysisReport:
    """
    Full pipeline:
    1. Parse all documents
    2. Extract allegations from primary witness
    3. Classify each allegation against each comparison witness
    4. Assemble matrix and report
    """
    print(f"\n=== PARSING DOCUMENTS ===")
    primary_doc = parse_document(primary_pdf)
    print(f"Primary: {primary_doc.witness_name}")

    comparison_docs = []
    for pdf in comparison_pdfs:
        doc = parse_document(pdf)
        comparison_docs.append(doc)
        print(f"Comparison: {doc.witness_name}")

    print(f"\n=== EXTRACTING ALLEGATIONS ===")
    allegations = extract_allegations(primary_doc)
    print(f"Found {len(allegations)} claims from {primary_doc.witness_name}")

    print(f"\n=== CLASSIFYING EVIDENCE ===")
    matrix = []

    for i, allegation in enumerate(allegations):
        print(f"[{i+1}/{len(allegations)}] Checking: {allegation.summary[:60]}...")

        supporting = []
        contradicting = []
        neutral = []
        not_addressed_count = 0

        for doc in comparison_docs:
            result = classify_against_witness(allegation, doc)

            if result.verdict == "SUPPORTS":
                supporting.append({
                    "witness": result.witness_b,
                    "passage": result.relevant_passage,
                    "paragraph": result.paragraph_ref,
                    "confidence": result.confidence
                })
            elif result.verdict == "CONTRADICTS":
                contradicting.append({
                    "witness": result.witness_b,
                    "passage": result.relevant_passage,
                    "paragraph": result.paragraph_ref,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning
                })
            elif result.verdict == "NEUTRAL":
                neutral.append(result.witness_b)
            else:
                not_addressed_count += 1

        gap = len(supporting) == 0 and len(contradicting) == 0

        # Overall confidence based on support
        if len(supporting) >= 2:
            confidence = "HIGH"
        elif len(supporting) == 1:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        matrix.append(MatrixRow(
            allegation_summary=allegation.summary,
            allegation_type=allegation.type,
            topic=allegation.topic,
            paragraph_ref=allegation.paragraph_ref,
            witness_a=allegation.witness_name,
            supporting=supporting,
            contradicting=contradicting,
            neutral=neutral,
            not_addressed=not_addressed_count,
            gap=gap,
            confidence=confidence
        ))

    trial_readiness, score = calculate_trial_readiness(matrix)
    gaps = [row for row in matrix if row.gap]
    contradictions = [row for row in matrix if len(row.contradicting) > 0]

    return AnalysisReport(
        primary_witness=primary_doc.witness_name,
        comparison_witnesses=[d.witness_name for d in comparison_docs],
        total_claims=len(allegations),
        matrix=matrix,
        trial_readiness=trial_readiness,
        trial_readiness_score=score,
        gaps=gaps,
        contradictions=contradictions
    )
