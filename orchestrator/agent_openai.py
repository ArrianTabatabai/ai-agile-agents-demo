import os
import json
import base64
from typing import Dict, Any, Optional
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-nano")

SYSTEM_PROMPT = """You are a careful software engineer.
Output ONLY valid JSON (no markdown, no commentary, no trailing text).

You MUST follow this schema exactly:
{
  "summary": "<short summary>",
  "files": [
    {"path": "<repo-relative path>", "content_b64": "<BASE64 ONLY>"},
    ...
  ]
}

Hard rules:
- content_b64 must be STANDARD base64 of the full UTF-8 file content.
- content_b64 must contain ONLY characters: A-Z a-z 0-9 + / =
- Do NOT include whitespace or newlines in content_b64.
- Do NOT use triple quotes.
- Keep changes small and focused.
"""

def generate_file_edits(
    issue_title: str,
    issue_body: str,
    repo_files: Dict[str, str],
    ci_feedback: Optional[str] = None
) -> Dict[str, Any]:
    files_block = "\n\n".join([f"--- FILE: {p} ---\n{c}" for p, c in repo_files.items()])
    feedback_block = f"\n\nCI FEEDBACK:\n{ci_feedback}\n" if ci_feedback else ""

    prompt = f"""
ISSUE TITLE:
{issue_title}

ISSUE BODY:
{issue_body}
{feedback_block}

REPO CONTEXT:
{files_block}

Note: CI runs hidden tests. You cannot modify tests or policy. Ensure changes are robust.

Before returning JSON, ensure every content_b64 is valid base64 with correct '=' padding and no newlines.

Return ONLY the JSON object described in the system prompt.
"""

    # Responses API (official)
    resp = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt,
    )
    text = resp.output_text

    # Parse strict JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Attempt salvage if there is leading/trailing noise
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise
        return json.loads(text[start:end+1])