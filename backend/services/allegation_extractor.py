import json
from clients.claude_client import call_claude
from dataclasses import dataclass

@dataclass
class Allegation:
    id: int
    type: str
    summary: str
    paragraph_ref: str
    parties_involved: list
    topic: str
    witness_name: str
    statement_number: str

def load_prompt() -> str:
    with open("backend/prompts/extract_allegations.txt", "r") as f:
        return f.read()

def extract_allegations(document) -> list[Allegation]:
    """
    Send a witness statement to Claude and get back
    a structured list of allegations/claims.
    Chunks long documents to stay within context limits.
    """
    prompt_template = load_prompt()

    # Limit to first 8000 chars for speed — covers most statements fully
    text_chunk = document.raw_text[:8000]

    prompt = f"""
{prompt_template}

WITNESS STATEMENT:
Witness: {document.witness_name}
Statement: {document.statement_number}

{text_chunk}
"""

    response = call_claude(
        prompt=prompt,
        system="You are a precise legal analyst. Always return valid JSON only.",
        max_tokens=4000
    )

    # Safely parse JSON
    try:
        raw = json.loads(response)
    except (json.JSONDecodeError, ValueError):
        # Try to extract just the JSON array if Claude added extra text
        import re
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            try:
                raw = json.loads(match.group())
            except json.JSONDecodeError:
                # Truncated JSON — extract whatever complete objects exist
                partial = match.group()
                complete = partial[:partial.rfind('}')+1] + ']'
                raw = json.loads(complete)
        else:
            print(f"WARNING: Could not parse Claude response for {document.witness_name}, returning empty")
            return []

    allegations = []
    for item in raw:
        allegations.append(Allegation(
            id=item.get("id", 0),
            type=item.get("type", "unknown"),
            summary=item.get("summary", ""),
            paragraph_ref=item.get("paragraph_ref", ""),
            parties_involved=item.get("parties_involved", []),
            topic=item.get("topic", "other"),
            witness_name=document.witness_name,
            statement_number=document.statement_number
        ))

    return allegations
