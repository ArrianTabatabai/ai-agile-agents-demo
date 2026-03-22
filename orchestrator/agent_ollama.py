import json
import requests
from typing import Dict, List, Any

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:7b"

SYSTEM_PROMPT = """You are a careful software engineer.
You must output ONLY valid JSON. No markdown. No commentary.

Return JSON in this exact shape:
{
  "summary": "<short summary>",
  "files": [
    {"path": "<repo-relative path>", "content_b64": "<BASE64 of full file content>"},
    ...
  ]
}

Note: CI runs hidden tests. You cannot modify tests or policy. Ensure changes are robust.

Rules:
- content_b64 MUST be base64 of the full file contents (UTF-8).
- Do NOT use triple quotes. Do NOT include raw multiline strings.
- Only edit files that are necessary.
- Keep changes small.
- Follow the Issue acceptance criteria exactly.
"""

def call_ollama(prompt: str, temperature: float = 0.2) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": temperature
        }
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=600)
    r.raise_for_status()
    data = r.json()
    return data["response"]

def generate_file_edits(issue_title: str, issue_body: str, repo_files: Dict[str, str], ci_feedback: str | None = None) -> Dict[str, Any]:
    """
    repo_files: mapping {path: content} for relevant files you want the model to consider.
    ci_feedback: optional failure summary for retry.
    """
    files_block = "\n\n".join(
        [f"--- FILE: {path} ---\n{content}" for path, content in repo_files.items()]
    )

    feedback_block = ""
    if ci_feedback:
        feedback_block = f"\n\nCI FEEDBACK (the previous attempt failed):\n{ci_feedback}\n"

    prompt = f"""
TASK:
You are working on a Git repo. Implement this GitHub Issue.

ISSUE TITLE:
{issue_title}

ISSUE BODY:
{issue_body}
{feedback_block}

REPO CONTEXT (current file contents):
{files_block}

OUTPUT REQUIREMENTS:
- Output ONLY valid JSON matching the schema described in the system prompt.
- Include FULL content for each file you modify (not diffs).
- Prefer editing existing files over creating many new ones.
"""

    raw = call_ollama(prompt, temperature=0.0)
    with open("orchestrator/logs/last_model_output.txt", "w", encoding="utf-8") as f:
        f.write(raw)
    # Be strict: JSON only
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Sometimes models include stray text. Try to salvage JSON by trimming.
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            raise
        result = json.loads(raw[start:end+1])

    # Minimal validation
    if "files" not in result or not isinstance(result["files"], list):
        raise ValueError("Model output missing 'files' list.")
    for f in result["files"]:
        if "path" not in f or "content_b64" not in f:
            raise ValueError("Each file item must have 'path' and 'content_b64'.")
    return result