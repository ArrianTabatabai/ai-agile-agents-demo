import os
import json
import re
from typing import Dict, Any, Optional
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")

# =============================================================================
# APPROACH: Instead of asking the model to base64-encode file content (which it
# gets wrong frequently), we ask it to return the file content as PLAIN TEXT
# inside clearly delimited markers. The orchestrator handles encoding.
#
# This eliminates the #1 source of corruption: bad base64 from the model.
# =============================================================================

SYSTEM_PROMPT = """You are a precise code-editing assistant.

TASK: You receive an issue description and the FULL content of source files.
You must return the COMPLETE, MODIFIED version of each changed file.

OUTPUT FORMAT — return ONLY this structure, nothing else:

<JSON>
{
  "summary": "<one-line summary of changes>"
}
</JSON>

Then, for EACH file you changed, output:

<FILE path="<repo-relative-path>">
<complete file content here, exactly as it should be saved>
</FILE>

CRITICAL RULES:
1. Inside each <FILE> block, include the ENTIRE file from first line to last.
   Include ALL imports, ALL classes, ALL functions — even ones you did not change.
2. Do NOT create new files. Only return files you were asked to edit.
3. Do NOT remove or rename any existing functions.
4. Keep changes MINIMAL — only what the issue asks for.
5. For app/rules.py: load_policy(), _matches(), and evaluate() MUST all appear.
   If ANY are missing, the change will be REJECTED.
6. Do NOT wrap file content in markdown code fences (no ```).
"""


def extract_json_block(text: str) -> str:
    start_tag = "<JSON>"
    end_tag = "</JSON>"
    start = text.find(start_tag)
    end = text.rfind(end_tag)
    if start == -1 or end == -1:
        s = text.find("{")
        e = text.rfind("}")
        if s == -1 or e == -1:
            raise ValueError("No JSON block found in model output.")
        return text[s : e + 1]
    return text[start + len(start_tag) : end].strip()


def extract_file_blocks(text: str) -> list[dict]:
    """
    Extract <FILE path="...">content</FILE> blocks from model output.
    Returns list of {"path": str, "content": str}.
    """
    pattern = r'<FILE\s+path="([^"]+)">\s*\n?(.*?)\n?\s*</FILE>'
    matches = re.findall(pattern, text, re.DOTALL)
    
    files = []
    for path, content in matches:
        # Strip leading/trailing whitespace but preserve internal structure
        content = content.strip("\n")
        # Remove markdown code fences if model added them despite instructions
        if content.startswith("```"):
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1 :]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip("\n")
        files.append({"path": path.strip(), "content": content})
    
    return files


def generate_file_edits(
    issue_title: str,
    issue_body: str,
    repo_files: Dict[str, str],
    ci_feedback: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns the same schema as before:
    {
        "summary": "...",
        "files": [{"path": "...", "content_b64": "..."}]
    }
    
    But internally uses plain-text output from the model and encodes here.
    This is a DROP-IN REPLACEMENT — orchestrator.py doesn't need changes.
    """
    import base64

    allowed_edit_files = {"app/rules.py", "site/index.html"}

    files_block = ""
    for path, content in repo_files.items():
        editable = "(EDITABLE)" if path in allowed_edit_files else "(READ-ONLY)"
        files_block += f"\n{'='*60}\n"
        files_block += f"FILE: {path}  {editable}\n"
        files_block += f"{'='*60}\n"
        files_block += content
        files_block += f"\n{'='*60} END OF {path} {'='*60}\n"

    feedback_block = ""
    if ci_feedback:
        feedback_block = f"""
--- CI FEEDBACK (previous attempt failed) ---
{ci_feedback}
--- END CI FEEDBACK ---
"""

    prompt = f"""ISSUE TITLE: {issue_title}

ISSUE BODY:
{issue_body}

{feedback_block}

REPOSITORY FILES (current versions):
{files_block}

REMINDERS:
- Return the COMPLETE file for every file you change (all imports, all functions).
- For app/rules.py: load_policy(), _matches(), evaluate() MUST ALL be present.
- Do NOT edit READ-ONLY files.
- Keep changes minimal.

Return the <JSON> summary block, then <FILE> blocks as described in the system prompt.
"""

    resp = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt,
    )
    text = resp.output_text

    # Extract summary
    json_text = extract_json_block(text)
    try:
        meta = json.loads(json_text)
    except json.JSONDecodeError:
        meta = {"summary": "Could not parse summary"}

    summary = meta.get("summary", "")

    # Extract file blocks (plain text) and encode to base64 ourselves
    file_blocks = extract_file_blocks(text)

    files_out = []
    for fb in file_blocks:
        path = fb["path"]
        content = fb["content"]
        # Encode to base64 — this is now done reliably by Python, not the LLM
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        files_out.append({"path": path, "content_b64": content_b64})

    return {"summary": summary, "files": files_out}