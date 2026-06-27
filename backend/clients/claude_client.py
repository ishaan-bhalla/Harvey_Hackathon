# backend/clients/claude_client.py

import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def call_claude(prompt: str, system: str = None, max_tokens: int = 2000) -> str:
    """
    Single function that wraps all Claude API calls.
    Every service in this project calls this — never calls Anthropic directly.

    Args:
        prompt: The user message to send
        system: Optional system prompt to set Claude's role
        max_tokens: Max length of response (default 2000)

    Returns:
        Claude's response as a plain string
    """
    messages = [{"role": "user", "content": prompt}]

    kwargs = {
        "model": "claude-opus-4-6",
        "max_tokens": max_tokens,
        "messages": messages
    }

    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    return response.content[0].text
