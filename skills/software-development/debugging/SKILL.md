---
name: debugging
description: "Debugging methodology and tool-specific guides: systematic root-cause investigation, Python (pdb/debugpy), and Node.js (inspect/CDP). Use when investigating bugs, test failures, or unexpected behavior."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, troubleshooting, root-cause, python, pdb, debugpy, nodejs, node-inspect, breakpoints]
    related_skills: [test-driven-development, requesting-code-review]
---

# Debugging

Two layers: **methodology** (how to think about debugging) and **tools** (how to use specific debuggers). Always start with the methodology, then pick the right tool.

## Quick Decision

| Situation | Use... |
|-----------|--------|
| Any bug — start here | § Systematic Methodology (below) |
| Python test fails, need to inspect state | § Python Debugging (pdb/debugpy) — see `references/python-debugpy.md` |
| Node.js/TUI crashes, need breakpoints | § Node.js Debugging (inspect/CDP) — see `references/node-inspect-debugger.md` |
| Long-running process misbehaves | Remote debug: `debugpy` (Python) or `kill -SIGUSR1` (Node) |

---

## Systematic Debugging Methodology

### The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

Random fixes waste time and create new bugs. Quick patches mask underlying issues. **ALWAYS find root cause before attempting fixes.**

### The Four Phases

#### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read error messages carefully** — don't skip past errors. Read stack traces completely. Note line numbers, file paths, error codes.
2. **Reproduce consistently** — can you trigger it reliably? What are exact steps? If not reproducible, gather more data.
3. **Check recent changes** — `git log --oneline -10`, `git diff`, new dependencies, config changes.
4. **Gather evidence in multi-component systems** — add diagnostic instrumentation at each component boundary. Log what enters/exits each component.
5. **Trace data flow** — where does the bad value originate? Keep tracing upstream until you find the source.

**Phase 1 checklist:**
- [ ] Error messages fully read and understood
- [ ] Issue reproduced consistently
- [ ] Recent changes identified
- [ ] Evidence gathered (logs, state, data flow)
- [ ] Problem isolated to specific component
- [ ] Root cause hypothesis formed

**STOP:** Do not proceed until you understand WHY it's happening.

#### Phase 2: Pattern Analysis

1. **Find working examples** — locate similar working code in the same codebase
2. **Compare against references** — read the reference implementation COMPLETELY
3. **Identify differences** — list every difference between working and broken
4. **Understand dependencies** — what settings, config, environment does this need?

#### Phase 3: Hypothesis and Testing

1. **Form a single hypothesis** — "I think X is the root cause because Y"
2. **Test minimally** — smallest possible change, one variable at a time
3. **Verify** — did it work? → Phase 4. Didn't? → new hypothesis. DON'T add more fixes on top.

#### Phase 4: Implementation

1. **Create failing test case** — simplest possible reproduction
2. **Implement single fix** — address root cause, ONE change at a time
3. **Verify fix** — run the regression test, then full suite
4. **Rule of Three** — if 3+ fixes failed, STOP and question the architecture

### Red Flags — STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "One more fix attempt" (when already tried 2+)
- Each fix reveals a new problem in a different place

**ALL of these mean: STOP. Return to Phase 1.**

### Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too |
| "Emergency, no time for process" | Systematic is FASTER than thrashing |
| "Just try this first, then investigate" | First fix sets the pattern |
| "Multiple fixes at once saves time" | Can't isolate what worked |

---

## Python Debugging (pdb + debugpy)

Three tools, picked by situation:

| Tool | When |
|------|------|
| `breakpoint()` + pdb | Local, interactive, simplest |
| `python -m pdb` | Launch script under pdb, no source edits |
| `debugpy` | Remote / headless / attach to running process |

**Start with `breakpoint()`.** It's the cheapest thing that works.

### pdb Quick Reference

| Command | Action |
|---------|--------|
| `n` | next line (step over) |
| `s` | step into |
| `r` | return from current function |
| `c` | continue |
| `l` / `ll` | list source / full function |
| `w` | where (stack trace) |
| `u` / `d` | up / down in stack |
| `p expr` / `pp expr` | print / pretty-print |
| `b file:line` | set breakpoint |
| `b file:line, cond` | conditional breakpoint |
| `!stmt` | execute arbitrary Python |
| `interact` | full REPL in current scope |
| `q` | quit |

### Recipes

**Local breakpoint:** Add `breakpoint()` in source, run normally. Don't forget to remove before committing.

**Debug pytest:**
```bash
pytest tests/test.py::test_name --pdb -p no:xdist
```

**Post-mortem:**
```python
import pdb, sys
try:
    run_the_thing()
except Exception:
    pdb.post_mortem(sys.exc_info()[2])
```

**Remote debug with debugpy:**
```python
import debugpy
debugpy.listen(("127.0.0.1", 5678))
debugpy.wait_for_client()
```

**No source edit:** `python -m debugpy --listen 127.0.0.1:5678 --wait-for-client your_script.py`

**Attach to running process:** `python -m debugpy --listen 127.0.0.1:5678 --pid <pid>`

**Cleanest terminal agent option:** `remote-pdb` — `pip install remote-pdb`, then `from remote_pdb import set_trace; set_trace(host="127.0.0.1", port=4444)` and `nc 127.0.0.1 4444`.

### Python Pitfalls

1. **pdb under pytest-xdist silently does nothing.** Always use `-p no:xdist` or `-n 0`.
2. **`breakpoint()` in CI hangs.** Safe locally; never commit it.
3. **`PYTHONBREAKPOINT=0`** disables all breakpoints. Check the env.
4. **debugpy attach fails on hardened kernels.** `echo 0 > /proc/sys/kernel/yama/ptrace_scope`
5. **pdb doesn't follow forks.** Each child needs its own breakpoint.

For the complete Python debugging reference, see `references/python-debugpy.md`.

---

## Node.js Debugging (inspect + CDP)

Two tools:

| Tool | When |
|------|------|
| `node inspect` | Built-in, zero install, CLI REPL |
| CDP via `chrome-remote-interface` | Scriptable, automated breakpoints |

**Prefer `node inspect` first.** Always available, fast REPL.

### node inspect Quick Reference

```bash
node --inspect-brk script.js    # Pause on first line
node inspect -p <pid>            # Attach to running process
```

| Command | Action |
|---------|--------|
| `c` | continue |
| `n` | step over |
| `s` | step into |
| `o` | step out |
| `pause` | pause running code |
| `sb('file.js', 42)` | set breakpoint |
| `cb('file.js', 42)` | clear breakpoint |
| `bt` | backtrace |
| `list(5)` | show source |
| `repl` | REPL in current scope |
| `exec expr` | evaluate expression |

### Attaching to Running Process

```bash
kill -SIGUSR1 <pid>              # Enable inspector
node inspect -p <pid>            # Attach
```

### Node Pitfalls

1. **Wrong line numbers in TS.** Breakpoints hit emitted JS. Use `node --enable-source-maps`.
2. **`--inspect` vs `--inspect-brk`.** Without `-brk`, script races past your breakpoint.
3. **Port collisions.** Use `--inspect=0` for random port.
4. **Child processes not inspected.** Use `NODE_OPTIONS='--inspect-brk'`.
5. **Source listing mismatch** = sourcemap issue.

For the complete Node.js debugging reference, see `references/node-inspect-debugger.md`.

---

## One-Shot Recipes

**"Why is this dict missing a key?"**
```python
breakpoint()  # above the KeyError site
# in pdb: pp d, pp list(d.keys()), w
```

**"This test passes in isolation but fails in the suite."**
```bash
python -m pytest tests/ -x --pdb -p no:xdist
```

**"My async handler deadlocks."**
```python
import remote_pdb; remote_pdb.set_trace(host="127.0.0.1", port=4444)
# nc 127.0.0.1 4444, then w to see suspended frame
```

**"What's the call path into this Node function?"**
```
debug> sb('suspectFn')
debug> cont
debug> bt
```
