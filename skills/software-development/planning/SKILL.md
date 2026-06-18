---
name: planning
description: "Software development planning: implementation plans and throwaway spikes. Use when the user wants a structured plan before building, or wants to validate an idea with a quick experiment."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [planning, plan-mode, implementation, spike, prototype, experiment, feasibility, workflow]
    related_skills: [test-driven-development, requesting-code-review, subagent-driven-development]
---

# Software Development Planning

Two complementary planning modes: **Plan** (structured implementation plan) and **Spike** (throwaway experiment to validate feasibility). Choose based on what the user needs.

## Quick Decision

| User says... | Use... | Output |
|-------------|--------|--------|
| "plan this out", "write a plan", "how should we build X" | **Plan mode** | Actionable markdown plan in `.hermes/plans/` |
| "let me try this", "is this even possible?", "spike this out", "compare A vs B" | **Spike mode** | Working prototype in `spikes/` with verdict |

---

## Plan Mode

Use when the user wants a plan instead of execution. Deliverable: a markdown plan saved to `.hermes/plans/`.

### Core behavior

- Do not implement code or edit project files (except the plan)
- Do not run mutating commands, commit, push, or perform external actions
- May inspect the repo with read-only tools
- Save to `.hermes/plans/YYYY-MM-DD_HHMMSS-<slug>.md`

### Writing a Good Plan

**Core principle:** A good plan makes implementation obvious. If someone has to guess, the plan is incomplete.

#### Bite-sized task granularity

Each task = 2-5 minutes of focused work. Every step is one action:
- "Write the failing test" — step
- "Run it to make sure it fails" — step
- "Implement the minimal code to make the test pass" — step
- "Run the tests and make sure they pass" — step
- "Commit" — step

#### Plan document structure

```markdown
# [Feature Name] Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** [One sentence]
**Architecture:** [2-3 sentences]
**Tech Stack:** [Key technologies]

---

### Task N: [Descriptive Name]

**Objective:** What this task accomplishes (one sentence)

**Files:**
- Create: `exact/path/to/new_file.py`
- Modify: `exact/path/to/existing.py:45-67`
- Test: `tests/path/to/test_file.py`

**Step 1: Write failing test**
[Complete, copy-pasteable test code]

**Step 2: Run test to verify failure**
Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL — "function not defined"

**Step 3: Write minimal implementation**
[Complete implementation code]

**Step 4: Run test to verify pass**
Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

**Step 5: Commit**
`git add tests/path/test.py src/path/file.py && git commit -m "feat: add specific feature"`
```

#### Principles

- **DRY** — extract shared logic, don't copy-paste
- **YAGNI** — implement only what's needed now
- **TDD** — every code task: write failing test → verify fail → implement → verify pass
- **Frequent commits** — commit after every task
- **Exact file paths** — not "the config file" but `src/config/settings.py`
- **Complete code** — copy-pasteable, not "add validation"
- **Exact commands with expected output**

#### Execution handoff

After saving: "Plan complete and saved. Ready to execute using subagent-driven-development — I'll dispatch a fresh subagent per task with two-stage review. Shall I proceed?"

---

## Spike Mode

Use when the user wants to **feel out an idea** before committing to a real build. Spikes are disposable by design.

### When NOT to use

- The answer is knowable from docs — just research, don't build
- The work is production path — use Plan mode instead
- The idea is already validated — jump to implementation

### Core method

```
decompose → research → build → verdict
   ↑__________________________________________↓
              iterate on findings
```

#### 1. Decompose

Break the idea into 2-5 independent feasibility questions. Present as a table:

| # | Spike | Validates (Given/When/Then) | Risk |
|---|-------|----------------------------|------|
| 001 | websocket-streaming | Given WS connection, when LLM streams tokens, then client receives chunks < 100ms | High |
| 002a | pdf-parse-pdfjs | Given multi-page PDF, when parsed with pdfjs, then structured text extractable | Medium |
| 002b | pdf-parse-camelot | Given multi-page PDF, when parsed with camelot, then structured text extractable | Medium |

**Spike types:** standard (one approach) or comparison (same question, different approaches with letter suffix a/b/c).

**Order by risk.** The spike most likely to kill the idea runs first.

#### 2. Research (per spike)

1. Brief it: 2-3 sentences on what and why
2. Surface competing approaches if there's real choice
3. Pick one and state why
4. Skip research for pure logic with no external dependencies

#### 3. Build

One directory per spike, standalone:

```
spikes/
├── 001-websocket-streaming/
│   ├── README.md
│   └── main.py
└── 002a-pdf-parse-pdfjs/
    ├── README.md
    └── parse.js
```

**Bias toward something the user can interact with.** Preference order:
1. Runnable CLI with observable output
2. Minimal HTML page demonstrating behavior
3. Small web server with one endpoint
4. Unit test with recognizable assertions

**Depth over speed.** Never declare "it works" after one happy-path run. Test edge cases.

#### 4. Verdict

Each spike's README closes with:

```markdown
## Verdict: VALIDATED | PARTIAL | INVALIDATED

### What worked
- ...

### What didn't
- ...

### Surprises
- ...

### Recommendation for the real build
- ...
```

**VALIDATED** = core question answered yes with evidence.
**PARTIAL** = works under constraints X, Y, Z.
**INVALIDATED** = doesn't work. This is a successful spike.

#### Comparison spikes

Build back-to-back, then head-to-head:

```markdown
## Head-to-head: pdfjs vs camelot

| Dimension | pdfjs (002a) | camelot (002b) |
|-----------|--------------|----------------|
| Extraction quality | 9/10 | 7/10 |
| Setup complexity | npm install | pip + ghostscript |

**Winner:** pdfjs for our use case.
```

---

## Common Mistakes

### Plan mode
- **Vague tasks:** "Add authentication" → "Create User model with email and password_hash fields"
- **Incomplete code:** "Add validation" without the actual code
- **Missing verification:** "Test it works" without exact commands
- **Missing file paths:** "Create the model file" without the path

### Spike mode
- **Too broad:** "Can we use AI?" → "Given a 10-page PDF, when parsed with pdfjs, is structured text extractable?"
- **No observable output:** A log line that says "it works" isn't enough
- **Production cleanup:** A spike that takes 2 days to "clean up for production" was a bad spike
- **Skipping research:** Don't build blindly; research enough to pick the right approach first
