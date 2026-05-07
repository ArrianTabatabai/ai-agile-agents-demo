# Feasibility and Analysis of AI Agents in Agile Software Development

This repository contains the implementation and experimental workflow for my dissertation project:

**Feasibility and Analysis of AI Agents in Agile Software Development**

The project investigates whether Large Language Model (LLM) agents can be integrated into a realistic software development workflow, and whether Agile-style task decomposition improves the quality and reliability of AI-generated code compared with single-shot prompting.

Rather than using an LLM only as a chat-based code generator, this project builds a workflow where an AI agent can:

1. Detect a labelled GitHub Issue.
2. Read the task description and selected repository context.
3. Generate code changes.
4. Create a branch.
5. Open a Pull Request.
6. Trigger CI tests.
7. Deploy a preview link.
8. Allow a human reviewer to validate the result.

The goal is to evaluate whether AI agents can fit into existing software engineering processes such as issue tracking, pull requests, automated testing, and preview-based review.

---

## Project Overview

The dissertation compares four approaches to giving work to an AI coding agent:

### Approach 1 - Zero Human Involvement

A single broad client-style brief is provided in one GitHub Issue.  
No decomposition, clarification, or follow-up guidance is provided.

### Approach 2 - Partial Human Involvement

The same broad project brief is provided, but decomposed into user stories and acceptance criteria within a single Issue.  
No further iteration is allowed.

### Approach 3 - Waterfall Then Iterate

The agent starts with the same full brief and user stories as Approach 2.  
If the result is incomplete or incorrect, follow-up intervention Issues are created until the implementation is accepted or blocked.

### Approach 4 - Agile Incremental

User stories are provided one at a time as separate GitHub Issues.  
Each story is implemented, tested, reviewed, and merged before the next story is attempted.

The central hypothesis is that AI agents perform better when work is broken into smaller, sequential, testable tasks.

---

## Repository Structure

```text
ai-agile-agents-demo/
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── pages-main.yml
│       └── pr-preview.yml
│
├── app/
│   └── rules.py
│
├── docs/
│   ├── policy.json
│   ├── metrics_template.md
│   └── results/
│
├── orchestrator/
│   ├── orchestrator.py
│   ├── agent_openai.py
│   └── agent_ollama.py
│
├── site/
│   ├── index.html
│   └── data/
│
├── tests/
│   └── test_rules.py
│
├── requirements.txt
└── README.md
````

---

## Core Components

### `orchestrator/orchestrator.py`

The main automation script. It:

* polls GitHub Issues;
* detects Issues labelled `ai:dev`;
* creates a new branch;
* calls the configured AI model backend;
* applies generated file changes;
* opens a Pull Request;
* monitors CI status;
* posts preview links;
* labels Issues as `ai:done` or `ai:blocked`;
* logs events for evaluation.

### `orchestrator/agent_openai.py`

OpenAI-based agent backend. It sends the Issue prompt and repository context to the selected OpenAI model and returns structured file edits.

### `orchestrator/agent_ollama.py`

Local Ollama-based backend used during earlier development and testing.

### `.github/workflows/ci.yml`

Runs automated tests on Pull Requests.

### `.github/workflows/pr-preview.yml`

Deploys a Pull Request preview using GitHub Pages, allowing a human reviewer to validate the output visually.

### `site/index.html`

The browser-based preview interface used for validating generated features.

### `docs/policy.json`

A fixed policy/specification file used in the decisioning project. The agent is not intended to modify this file during controlled experiments.

### `tests/`

Hidden automated tests used to evaluate correctness. These are not provided to the model as part of the prompt context.

---

## Experimental Projects

Two projects were used during evaluation.

### Project A - Policy-Driven Decision Engine

A small loan decisioning tool where applicants are evaluated against a fixed policy.
The system must show decisions, triggered reasons, and reviewer-friendly explanations.

This project tests whether an AI agent can correctly modify business logic and a preview interface while respecting hidden tests and fixed policy rules.

### Project B - AI-Assisted Loan Underwriting Workspace

A larger dashboard-style application for internal credit analysts.
The application includes applicant selection, policy explanations, risk scoring, risk bands, what-if scenarios, applicant comparison, portfolio summaries, and generated underwriting notes.

This project tests whether workflow structure matters more as project complexity increases.

---

## Labels Used

The orchestrator uses GitHub Issue labels to manage workflow state.

| Label            | Meaning                                                    |
| ---------------- | ---------------------------------------------------------- |
| `ai:dev`         | Issue is ready for the agent to process                    |
| `ai:in-progress` | Agent has started processing the Issue                     |
| `ai:done`        | Agent completed the task and CI/preview workflow succeeded |
| `ai:blocked`     | Agent failed, hit a guardrail, or CI did not pass          |

Only one Issue should normally have the `ai:dev` label at a time during controlled experiments.

---

## Guardrails

The orchestrator includes guardrails to prevent unsafe or invalid agent outputs.

Examples include:

* blocking edits to tests;
* blocking edits to fixed specification files;
* restricting editable files;
* detecting no-op outputs;
* preventing empty file overwrites;
* detecting non-printable characters;
* blocking destructive rewrites;
* ensuring required functions are not removed;
* marking failed runs as `ai:blocked`.

These guardrails are important because the project evaluates not only model capability, but also workflow safety.

---

## Metrics Collected

The experiments track both automated and manual metrics.

### Automated Metrics

* CI pass/fail result;
* number of retries;
* session duration;
* files changed;
* diff size;
* guardrail triggers;
* final Issue label.

### Manual Validation Metrics

* acceptance criteria coverage;
* preview usability;
* whether the output was accepted or rejected;
* number of human interventions;
* type of failure observed.

The key metric for comparing Approach 3 and Approach 4 is the number of human interventions required to reach an acceptable implementation.

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/ArrianTabatabai/ai-agile-agents-demo.git
cd ai-agile-agents-demo
```

### 2. Create and activate a virtual environment

On Windows:

```bat
python -m venv .venv
.venv\Scripts\activate
```

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set required environment variables

For OpenAI backend:

```bat
set AGENT_BACKEND=openai
set OPENAI_MODEL=gpt-5-mini
set OPENAI_API_KEY=YOUR_OPENAI_API_KEY
```

For a persistent Windows environment variable:

```bat
setx OPENAI_API_KEY "YOUR_OPENAI_API_KEY"
setx AGENT_BACKEND "openai"
setx OPENAI_MODEL "gpt-5-mini"
```

Close and reopen Command Prompt after using `setx`.

For GitHub API access:

```bat
set GITHUB_TOKEN=YOUR_GITHUB_TOKEN
```

or persistently:

```bat
setx GITHUB_TOKEN "YOUR_GITHUB_TOKEN"
```

---

## Running the Orchestrator

Before running the orchestrator:

1. Create a GitHub Issue containing the task.
2. Add the label `ai:dev`.
3. Make sure no other old Issues still have `ai:dev`.
4. Set the target base branch.

Example:

```bat
cd "C:\Users\bahar\Cardiff Uni\Final Year\Diss\Code\ai-agile-agents-demo"
.venv\Scripts\activate
set AGENT_BACKEND=openai
set OPENAI_MODEL=gpt-5-mini
set BASE_BRANCH=demo-run
python -m orchestrator.orchestrator
```

The orchestrator will then:

1. Detect the Issue.
2. Create a branch.
3. Generate code changes.
4. Open a Pull Request.
5. Wait for CI.
6. Post the result back to the Issue.

---

## Example Demo Issue

Use this Issue for a short demonstration run:

```text
[DEMO] Add reviewer guidance panel to loan preview dashboard

Upgrade the loan preview page so that a human reviewer can more easily understand the decision.

Allowed edits:
- You may edit site/index.html
- You may edit app/rules.py only if needed
- Do not edit docs/policy.json
- Do not edit tests
- Do not create new files

Task:
Add a reviewer guidance panel to the preview page.

The panel should show:
- final decision
- a short plain-English explanation of the result
- all triggered reasons, if any
- a recommendation for what the reviewer should do next

Recommendation logic:
- If decision is approve, recommend: "Proceed with approval checks."
- If decision is refer, recommend: "Send for manual review."
- If decision is reject, recommend: "Decline or escalate according to policy."

Acceptance criteria:
- Preview page still loads
- Existing applicant selection still works
- Evaluation still works
- Reviewer guidance panel is visible after evaluation
- Recommendation text matches the decision
- CI passes
- Preview link is posted on this issue
```

Add label:

```text
ai:dev
```

Then run:

```bat
set BASE_BRANCH=demo-run
python -m orchestrator.orchestrator
```

---

## Expected Workflow

```text
GitHub Issue labelled ai:dev
        ↓
Python orchestrator detects Issue
        ↓
AI agent generates code changes
        ↓
Branch is created
        ↓
Pull Request is opened
        ↓
CI tests run
        ↓
Preview link is posted
        ↓
Human reviewer validates the output
        ↓
Issue marked ai:done or ai:blocked
```

---

## Notes on Experimental Methodology

This project intentionally compares different levels of human involvement.

A failed or blocked run is still a useful result because it shows where the workflow, model, prompt, or guardrails were insufficient.

The purpose of the project is not only to produce working code, but to evaluate when AI agents become reliable enough to participate in a software engineering workflow.

---

## Dissertation Findings Summary

The evaluation suggested that:

* single broad prompts were less reliable;
* decomposed user stories improved clarity;
* iterative correction helped recover from failure;
* Agile-style incremental delivery required fewer interventions;
* CI and preview validation were essential for making agent output reviewable;
* guardrails were necessary to prevent unsafe or irrelevant changes;
* agent reliability depended heavily on workflow design, not only model capability.

---

## Limitations

This repository is a dissertation prototype and is not intended for production use.

Known limitations include:

* limited project scale;
* static preview deployment;
* model output variability;
* reliance on hidden tests;
* limited evaluation across programming languages;
* local execution of the orchestrator.

---

## Future Work

Potential improvements include:

* patch-based edits instead of full-file rewrites;
* more robust CI feedback extraction;
* support for container-based preview deployments;
* evaluation across more programming languages and frameworks;
* repeated trials for stronger statistical confidence;
* comparison across multiple LLM backends;
* integration with GitHub webhooks rather than local polling.

---

## Author

**Arrian Ghassemy Tabatabai**

Dissertation project:
**Feasibility and Analysis of AI Agents in Agile Software Development**
