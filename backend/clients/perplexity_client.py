import os
import requests
from dotenv import load_dotenv

load_dotenv()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

def search_case_law(allegation: str, topic: str) -> dict:
    query = f"""Find UK case law and legal precedents relevant to this Post Office Horizon IT Inquiry allegation: "{allegation}". Focus on: 1) UK court cases involving {topic.replace('_', ' ')} 2) Legal principles established 3) How precedents apply. Name actual cases with citations like [2023] EWHC 123."""

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "You are a UK litigation lawyer specialising in technology disputes. Provide precise case citations. Be concise — 3-4 sentences maximum."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        "max_tokens": 400,
        "return_citations": True
    }

    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        citations = data.get("citations", [])
        return {
            "case_law": content,
            "sources": citations[:3],
            "error": None
        }
    except Exception as e:
        return {
            "case_law": None,
            "sources": [],
            "error": str(e)
        }
