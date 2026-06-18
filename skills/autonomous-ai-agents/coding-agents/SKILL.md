---
name: coding-agents
description: "Delegate coding to external AI agent CLIs: Claude Code (Anthropic), Codex (OpenAI), and OpenCode. Use when orchestrating external coding agents for features, refactoring, PR reviews, or batch work."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [coding-agent, claude-code, codex, opencode, autonomous, refactoring, code-review, pty, automation]
    related_skills: [hermes-agent, github-pr-workflow, github-code-review]
---

# External Coding Agents

Delegate coding tasks to external AI agent CLIs via the Hermes terminal. Three agents are supported — choose based on what's installed and what the task needs.

## Choosing an Agent

| Agent | Provider | Auth | Best for | Install |
|-------|----------|------|----------|---------|
| **Claude Code** | Anthropic | OAuth or `ANTHROPIC_API_KEY` | Complex multi-step work, deep reasoning, interactive sessions | `npm install -g @anthropic-ai/claude-code` |
| **Codex** | OpenAI | `OPENAI_API_KEY` or OAuth | Quick one-shot tasks, batch issue fixing, parallel worktrees | `npm install -g @openai/codex` |
| **OpenCode** | Provider-agnostic | Various env vars | Provider flexibility, cost control, open-source | `npm i -g opencode-ai@latest` |

**Decision factors:**
- Need structured JSON output? → Claude Code (`--output-format json --json-schema`)
- Need parallel worktrees? → Codex (built-in worktree support)
- Need provider flexibility? → OpenCode (works with OpenRouter, Anthropic, OpenAI, etc.)
- Need interactive multi-turn? → Claude Code (richest TUI with slash commands)
- Need the cheapest option? → OpenCode (swap models freely)

## Shared Orchestration Pattern

All three agents follow the same Hermes integration pattern:

### One-shot (non-interactive, preferred for most tasks)
```
terminal(command="<agent> <one-shot-flags> 'task description'", workdir="/path/to/project", timeout=120)
```

### Background (long tasks)
```
terminal(command="<agent> <flags>", workdir="/path/to/project", background=true, pty=true)
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")
```

### Parallel instances
```
# Task 1
terminal(command="<agent> 'fix backend bug'", workdir="/project", background=true, pty=true)
# Task 2
terminal(command="<agent> 'write frontend tests'", workdir="/project", background=true, pty=true)
# Monitor all
process(action="list")
```

---

## Claude Code

**Install:** `npm install -g @anthropic-ai/claude-code`
**Auth:** Run `claude` once for browser OAuth, or set `ANTHROPIC_API_KEY`

### Print Mode (non-interactive, PREFERRED)
```
terminal(command="claude -p 'Add error handling to all API calls in src/' --allowedTools 'Read,Edit' --max-turns 10", workdir="/project", timeout=120)
```

Print mode skips ALL interactive dialogs. Returns JSON with `session_id`, `num_turns`, `total_cost_usd`.

### Structured JSON Output
```
terminal(command="claude -p 'Analyze auth.py' --output-format json --max-turns 5", workdir="/project", timeout=120)
```

### JSON Schema for Structured Extraction
```
terminal(command="claude -p 'List all functions' --output-format json --json-schema '{...}' --max-turns 5", workdir="/project", timeout=90)
```

### Interactive PTY via tmux
```
terminal(command="tmux new-session -d -s claude-work -x 140 -y 40")
terminal(command="tmux send-keys -t claude-work 'cd /path/to/project && claude' Enter")
terminal(command="sleep 5 && tmux send-keys -t claude-work 'Your task here' Enter")
terminal(command="sleep 15 && tmux capture-pane -t claude-work -p -S -50")
```

### PTY Dialog Handling
- **Trust dialog:** `tmux send-keys Enter` (default is "Yes")
- **Permissions dialog:** `tmux send-keys Down && sleep 0.3 && tmux send-keys Enter` (default is "No")

### Key Flags

| Flag | Effect |
|------|--------|
| `-p` | Non-interactive one-shot mode |
| `--max-turns N` | Limit agentic loops (print mode only) |
| `--max-budget-usd N` | Cap API spend |
| `--allowedTools` | Whitelist tools (Read, Edit, Write, Bash) |
| `--output-format json` | Structured JSON output |
| `--json-schema` | Force output matching schema |
| `--bare` | Skip hooks, plugins, MCP, CLAUDE.md (fastest) |
| `--effort low/medium/high/max` | Reasoning depth |
| `--model sonnet/opus/haiku` | Model selection |
| `--fallback-model` | Auto-fallback on overload |

### Session Continuation
```
# Resume most recent
claude -p 'Continue' --continue --max-turns 5
# Resume specific
claude -p 'Continue' --resume <session_id> --max-turns 5
```

For the complete Claude Code reference (all CLI flags, slash commands, hooks, MCP, custom agents, keyboard shortcuts), see `references/claude-code.md`.

---

## Codex

**Install:** `npm install -g @openai/codex`
**Auth:** `OPENAI_API_KEY` or Codex OAuth from login flow
**Requires git repo** — Codex refuses to run outside one

### One-Shot Tasks
```
terminal(command="codex exec 'Add dark mode toggle to settings'", workdir="/project", pty=true)
```

For scratch work: `cd $(mktemp -d) && git init && codex exec 'Build a snake game in Python'`

### Background Mode
```
terminal(command="codex exec --full-auto 'Refactor the auth module'", workdir="/project", background=true, pty=true)
process(action="poll", session_id="<id>")
process(action="submit", session_id="<id>", data="yes")  # If Codex asks
```

### Key Flags

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot execution, exits when done |
| `--full-auto` | Sandboxed but auto-approves file changes |
| `--yolo` | No sandbox, no approvals (fastest, most dangerous) |

### PR Reviews
```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main", pty=true)
```

### Parallel Worktrees
```
terminal(command="git worktree add -b fix/issue-78 /tmp/issue-78 main", workdir="/project")
terminal(command="codex --yolo exec 'Fix issue #78. Commit when done.'", workdir="/tmp/issue-78", background=true, pty=true)
```

### Rules
1. Always use `pty=true` — Codex is interactive
2. Git repo required
3. Use `exec` for one-shots
4. `--full-auto` for building
5. Background for long tasks

---

## OpenCode

**Install:** `npm i -g opencode-ai@latest` or `brew install anomalyco/tap/opencode`
**Auth:** `opencode auth login` or set provider env vars

### One-Shot Tasks (no pty needed)
```
terminal(command="opencode run 'Add retry logic to API calls and update tests'", workdir="/project")
```

### With context files
```
terminal(command="opencode run 'Review config for security' -f config.yaml -f .env.example", workdir="/project")
```

### Interactive Sessions (background)
```
terminal(command="opencode", workdir="/project", background=true, pty=true)
process(action="submit", session_id="<id>", data="Implement OAuth refresh flow")
process(action="poll", session_id="<id>")
# Exit with Ctrl+C (NOT /exit)
process(action="write", session_id="<id>", data="\x03")
```

### Key Flags

| Flag | Use |
|------|-----|
| `run 'prompt'` | One-shot execution |
| `--continue` / `-c` | Continue last session |
| `--session <id>` / `-s` | Continue specific session |
| `--model provider/model` | Force model |
| `--thinking` | Show model thinking |
| `--variant high/max/minimal` | Reasoning effort |

### PR Review
```
terminal(command="opencode pr 42", workdir="/project", pty=true)
```

### Pitfalls
- `/exit` is NOT valid — opens agent selector. Use Ctrl+C.
- `opencode run` does NOT need pty; interactive `opencode` does.
- Enter may need to be pressed twice in TUI.

---

## Common Rules for All Agents

1. **Prefer one-shot/non-interactive mode** for single tasks — cleaner, no dialog handling
2. **Use tmux for multi-turn interactive work** — the only reliable way to orchestrate TUIs
3. **Always set `workdir`** — keep the agent focused on the right project
4. **Set iteration limits** — prevents infinite loops and runaway costs
5. **Monitor background sessions** — check progress with `poll`/`log`
6. **Clean up tmux sessions** — kill when done
7. **Report results to user** — summarize what the agent did and what changed
8. **Use tool restrictions** — limit capabilities to what the task needs
9. **Don't kill slow sessions** — agent may be doing multi-step work
