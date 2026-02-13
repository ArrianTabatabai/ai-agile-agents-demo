import os, time, json, requests
from datetime import datetime, timezone

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

def process_issue(issue):
    issue_number = issue["number"]
    log({"event": "issue_detected", "issue": issue_number, "url": issue["html_url"]})

    add_labels(issue_number, [IN_PROGRESS_LABEL])
    log({"event": "label_added", "issue": issue_number, "label": IN_PROGRESS_LABEL})

    base_sha = get_branch_head_sha(BASE_BRANCH)
    branch = f"ai/issue-{issue_number}"
    create_branch(branch, base_sha)
    log({"event": "branch_created", "issue": issue_number, "branch": branch})

    note_path = f"ai_notes/issue-{issue_number}.md"
    note = f"# Placeholder\n\nThis proves issue->branch->PR->CI.\n\nIssue: #{issue_number}\n"
    create_file_on_branch(branch, note_path, note, f"AI: placeholder commit for issue #{issue_number}")
    log({"event": "commit_pushed", "issue": issue_number, "branch": branch, "file": note_path})

    pr = open_pr(branch, f"AI: Placeholder PR for issue #{issue_number}", f"Automated PR for #{issue_number}.")
    pr_num = pr["number"]
    head_sha = pr["head"]["sha"]
    log({"event": "pr_opened", "issue": issue_number, "pr": pr_num, "pr_url": pr["html_url"], "sha": head_sha})

    comment(issue_number, f"Opened PR: {pr['html_url']}")
    log({"event": "issue_commented", "issue": issue_number})

    # Poll CI status
    for i in range(30):
        status = get_check_runs(head_sha)
        log({"event": "ci_polled", "issue": issue_number, "pr": pr_num, "attempt": i+1,
             "ci_status": status["status"], "ci_conclusion": status["conclusion"]})

        if status["status"] == "completed" and status["conclusion"] in ("success", "failure"):
            conclusion = status["conclusion"]

            comment(issue_number, f"CI result: **{conclusion}**")
            log({"event": "ci_final", "issue": issue_number, "pr": pr_num, "conclusion": conclusion})

            # Label outcome for visible state transitions
            if conclusion == "success":
                add_labels(issue_number, ["ai:done"])
                log({"event": "label_added", "issue": issue_number, "label": "ai:done"})
            else:
                add_labels(issue_number, ["ai:blocked"])
                log({"event": "label_added", "issue": issue_number, "label": "ai:blocked"})

            break


        time.sleep(POLL_SECONDS)

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