import os
import json
import base64
from typing import Dict, Any, Optional
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-nano")

SYSTEM_PROMPT = """Output ONLY this format:

<JSON>
{...valid JSON...}
</JSON>

The JSON schema must be:
{
  "summary": "<short summary>",
  "files": [
    {"path": "<repo-relative path>", "content_b64": "<base64 UTF-8 full content>"},
    ...
  ]
}

Rules:
- content_b64 must contain ONLY base64 characters A-Z a-z 0-9 + / =
- No whitespace/newlines in content_b64.
- No extra keys.
- Do not create new files.
- Only edit allowed files.
"""

def extract_json_block(text: str) -> str:
    start_tag = "<JSON>"
    end_tag = "</JSON>"
    start = text.find(start_tag)
    end = text.rfind(end_tag)
    if start == -1 or end == -1:
        # fallback: try raw {...}
        s = text.find("{")
        e = text.rfind("}")
        if s == -1 or e == -1:
            raise ValueError("No JSON block found in model output.")
        return text[s:e+1]
    return text[start+len(start_tag):end].strip()

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

    # Parse strict JSON from the <JSON>...</JSON> wrapper
    json_text = extract_json_block(text)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        # Fallback salvage: last-resort trim to {...} inside extracted block
        start = json_text.find("{")
        end = json_text.rfind("}")
        if start == -1 or end == -1:
            raise
        return json.loads(json_text[start:end+1])