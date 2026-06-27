import os
import time
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def call_claude(prompt: str, system: str = None, max_tokens: int = 2000, retries: int = 3) -> str:
    """
    Single entry point for all Claude API calls.
    Retries up to 3 times on failure with exponential backoff.
    """
    messages = [{"role": "user", "content": prompt}]

    kwargs = {
        "model": "claude-opus-4-6",
        "max_tokens": max_tokens,
        "messages": messages
    }

    if system:
        kwargs["system"] = system

    last_error = None
    for attempt in range(retries):
        try:
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            last_error = e
            wait = 2 ** attempt  # 1s, 2s, 4s
            print(f"Claude API attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)

    raise Exception(f"Claude API failed after {retries} attempts: {last_error}")
