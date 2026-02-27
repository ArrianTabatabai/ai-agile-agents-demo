import os, time, json, requests
from datetime import datetime, timezone
from orchestrator.agent_ollama import generate_file_edits
import base64

OWNER = "ArrianTabatabai"
REPO = "ai-agile-agents-demo"
BASE_BRANCH = "main"

TRIGGER_LABEL = "ai:dev"
IN_PROGRESS_LABEL = "ai:in-progress"
POLL_SECONDS = 20

LOG_PATH = os.path.join("orchestrator", "logs", "events.jsonl")

session = requests.Session()
session.headers.update({
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
    "X-GitHub-Api-Version": "2022-11-28",
})

def log(event: dict):
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    print(json.dumps(event, indent=2))

def gh(url, method="GET", **kwargs):
    r = session.request(method, url, **kwargs)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {url} -> {r.status_code}: {r.text}")
    return r.json() if r.text else None

def repo_url(path: str) -> str:
    return f"https://api.github.com/repos/{OWNER}/{REPO}{path}"

def list_trigger_issues():
    q = f"repo:{OWNER}/{REPO} is:issue is:open label:\"{TRIGGER_LABEL}\" -label:\"{IN_PROGRESS_LABEL}\""
    data = gh("https://api.github.com/search/issues", params={"q": q, "per_page": 5})
    return data["items"]

def add_labels(issue_number: int, labels: list[str]):
    gh(repo_url(f"/issues/{issue_number}/labels"), method="POST", json={"labels": labels})

def comment(issue_number: int, body: str):
    gh(repo_url(f"/issues/{issue_number}/comments"), method="POST", json={"body": body})

def get_branch_head_sha(branch: str) -> str:
    ref = gh(repo_url(f"/git/ref/heads/{branch}"))
    return ref["object"]["sha"]

def create_branch(new_branch: str, from_sha: str):
    gh(repo_url("/git/refs"), method="POST", json={"ref": f"refs/heads/{new_branch}", "sha": from_sha})

def create_file_on_branch(branch: str, path: str, content: str, message: str):
    import base64
    b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    gh(repo_url(f"/contents/{path}"), method="PUT", json={
        "message": message,
        "content": b64,
        "branch": branch
    })

def open_pr(branch: str, title: str, body: str):
    return gh(repo_url("/pulls"), method="POST", json={
        "title": title, "head": branch, "base": BASE_BRANCH, "body": body
    })

def get_check_runs(sha: str):
    data = gh(repo_url(f"/commits/{sha}/check-runs"), params={"per_page": 50})
    runs = data.get("check_runs", [])
    if not runs:
        return {"status": "no-checks-yet", "conclusion": None, "runs": []}

    statuses = [r.get("status") for r in runs]
    conclusions = [r.get("conclusion") for r in runs]

    if any(s in ("queued", "in_progress") for s in statuses):
        return {"status": "in_progress", "conclusion": None, "runs": runs}

    # Completed
    if any(c in ("failure", "cancelled", "timed_out", "action_required") for c in conclusions):
        return {"status": "completed", "conclusion": "failure", "runs": runs}

    if all(c == "success" for c in conclusions if c is not None):
        return {"status": "completed", "conclusion": "success", "runs": runs}

    return {"status": "completed", "conclusion": "neutral", "runs": runs}

def get_file_content(path: str, ref: str = BASE_BRANCH) -> str:
    """Fetch a file from GitHub repo at a given ref (branch)."""
    data = gh(repo_url(f"/contents/{path}"), params={"ref": ref})
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    raise RuntimeError(f"Unexpected encoding for {path}")

def upsert_file(branch: str, path: str, content: str, message: str):
    """Create or update file on a branch using GitHub Contents API."""
    b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    url = repo_url(f"/contents/{path}")

    # Try fetch existing file to get sha (required to update)
    sha = None
    try:
        existing = gh(url, params={"ref": branch})
        sha = existing.get("sha")
    except RuntimeError as e:
        if "404" not in str(e):
            raise

    payload = {
        "message": message,
        "content": b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    gh(url, method="PUT", json=payload)

def process_issue(issue):
    issue_number = issue["number"]
    issue_title = issue.get("title") or f"Issue {issue_number}"
    issue_body = issue.get("body") or ""

    log({"event": "issue_detected", "issue": issue_number, "title": issue_title, "url": issue["html_url"]})

    # Mark in-progress
    add_labels(issue_number, [IN_PROGRESS_LABEL])
    log({"event": "label_added", "issue": issue_number, "label": IN_PROGRESS_LABEL})

    # Create branch from main
    base_sha = get_branch_head_sha(BASE_BRANCH)
    branch = f"ai/issue-{issue_number}"
    create_branch(branch, base_sha)
    log({"event": "branch_created", "issue": issue_number, "branch": branch, "base_sha": base_sha})

    # Minimal repo context bundle (keep small/reliable)
    repo_context = {
        "app/main.py": get_file_content("app/main.py", ref=BASE_BRANCH),
        "tests/test_smoke.py": get_file_content("tests/test_smoke.py", ref=BASE_BRANCH),
        "requirements.txt": get_file_content("requirements.txt", ref=BASE_BRANCH),
    }

    max_attempts = 2
    ci_feedback = None
    pr_num = None
    pr_url = None
    head_sha = None

    for attempt in range(1, max_attempts + 1):
        log({"event": "agent_attempt_start", "issue": issue_number, "attempt": attempt})

        # Ask local LLM (Ollama) for edits
        result = generate_file_edits(
            issue_title=issue_title,
            issue_body=issue_body,
            repo_files=repo_context,
            ci_feedback=ci_feedback
        )

        summary = (result.get("summary") or "").strip()
        files = result["files"]

        # Guardrail: keep diffs small
        if len(files) > 3:
            log({"event": "guardrail_triggered", "issue": issue_number, "attempt": attempt,
                 "reason": "too_many_files", "count": len(files)})
            comment(issue_number, f"Blocked: model attempted to change too many files ({len(files)}).")
            add_labels(issue_number, ["ai:blocked"])
            return

        changed_paths = []
        for f in files:
            path = f["path"].strip()
            content = f["content"]

            # Another guardrail: avoid weird paths
            if path.startswith("/") or ".." in path:
                log({"event": "guardrail_triggered", "issue": issue_number, "attempt": attempt,
                     "reason": "invalid_path", "path": path})
                comment(issue_number, f"Blocked: invalid file path from model: {path}")
                add_labels(issue_number, ["ai:blocked"])
                return

            upsert_file(
                branch=branch,
                path=path,
                content=content,
                message=f"AI: attempt {attempt} for issue #{issue_number}"
            )
            changed_paths.append(path)

        log({"event": "agent_changes_pushed", "issue": issue_number, "attempt": attempt,
             "files": changed_paths, "summary": summary})

        # On attempt 1: open PR. On attempt 2: find existing PR.
        if attempt == 1:
            pr = open_pr(
                branch,
                f"AI: {issue_title} (#{issue_number})",
                f"Automated PR for #{issue_number}.\n\nSummary: {summary}\n\nFiles: {', '.join(changed_paths)}"
            )
            pr_num = pr["number"]
            pr_url = pr["html_url"]
            head_sha = pr["head"]["sha"]

            log({"event": "pr_opened", "issue": issue_number, "pr": pr_num, "pr_url": pr_url, "sha": head_sha})
            comment(issue_number, f"Opened PR: {pr_url}")
            log({"event": "issue_commented", "issue": issue_number, "comment": "PR link posted"})
        else:
            prs = gh(repo_url("/pulls"), params={"state": "open", "head": f"{OWNER}:{branch}"})
            if not prs:
                raise RuntimeError("Retry attempt: could not find existing open PR for branch.")
            pr_num = prs[0]["number"]
            pr_url = prs[0]["html_url"]
            head_sha = prs[0]["head"]["sha"]

            log({"event": "pr_found_for_retry", "issue": issue_number, "pr": pr_num, "pr_url": pr_url, "sha": head_sha})

        # Poll CI status
        final_conclusion = None
        last_status = None
        for poll in range(30):
            status = get_check_runs(head_sha)
            last_status = status
            log({"event": "ci_polled", "issue": issue_number, "pr": pr_num, "attempt": attempt, "poll": poll + 1,
                 "ci_status": status["status"], "ci_conclusion": status["conclusion"]})

            if status["status"] == "completed" and status["conclusion"] in ("success", "failure"):
                final_conclusion = status["conclusion"]
                break

            time.sleep(POLL_SECONDS)

        # If CI never completed, treat as blocked (keeps Week 4 simple)
        if final_conclusion is None:
            comment(issue_number, f"Blocked: CI did not complete in time for PR {pr_url}")
            add_labels(issue_number, ["ai:blocked"])
            log({"event": "agent_blocked_ci_timeout", "issue": issue_number, "pr": pr_num})
            return

        # Success path
        if final_conclusion == "success":
            comment(issue_number, f"CI result: **success** (attempt {attempt})")

            preview_url = f"https://{OWNER}.github.io/{REPO}/pr-preview/pr-{pr_num}/"
            comment(issue_number, f"✅ Preview deployed: {preview_url}\n\nHuman review: open the link and validate acceptance criteria.")
            log({"event": "preview_link_posted", "issue": issue_number, "pr": pr_num, "preview_url": preview_url})

            add_labels(issue_number, ["ai:done"])
            log({"event": "agent_success", "issue": issue_number, "pr": pr_num, "attempt": attempt})
            return

        # Failure path (retry once)
        comment(issue_number, f"CI result: **failure** (attempt {attempt})")
        log({"event": "agent_ci_failure", "issue": issue_number, "pr": pr_num, "attempt": attempt})

        if attempt < max_attempts:
            # Give the model minimal, structured feedback based on check runs.
            failed_runs = []
            for r in (last_status.get("runs") or []):
                name = r.get("name")
                concl = r.get("conclusion")
                if concl and concl != "success":
                    failed_runs.append(f"{name}={concl}")

            ci_feedback = "CI failed. Failed checks: " + (", ".join(failed_runs) if failed_runs else "unknown") + \
                          ". Fix the code so `pytest -q` passes. Keep changes minimal."

            # Refresh repo context from the BRANCH for files the model just edited,
            # so attempt 2 sees the latest state.
            for p in changed_paths:
                try:
                    repo_context[p] = get_file_content(p, ref=branch)
                except Exception:
                    pass

            log({"event": "agent_retry_prepared", "issue": issue_number, "next_attempt": attempt + 1,
                 "ci_feedback": ci_feedback})
        else:
            add_labels(issue_number, ["ai:blocked"])
            log({"event": "agent_failed", "issue": issue_number, "pr": pr_num})
            return

def main():
    log({"event": "orchestrator_started", "mode": "single-run"})

    try:
        issues = list_trigger_issues()
        if not issues:
            log({"event": "no_trigger_issues"})
            return

        # Process exactly one issue, then exit
        process_issue(issues[0])
        log({"event": "single_run_complete"})
        return

    except Exception as e:
        log({"event": "error", "message": str(e)})
        return

if __name__ == "__main__":
    main()