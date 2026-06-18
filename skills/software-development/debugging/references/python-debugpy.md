# Python Debugging Deep Reference

Extended reference for Python debugging with pdb and debugpy. For the quick reference and methodology, see the main `debugging` skill.

## debugpy Setup Patterns

### Pattern A: Source-edit — process waits at launch
```python
import debugpy
debugpy.listen(("127.0.0.1", 5678))
print("debugpy listening on 5678, waiting for client...", flush=True)
debugpy.wait_for_client()
debugpy.breakpoint()
```

### Pattern B: No source edit — launch with -m debugpy
```bash
python -m debugpy --listen 127.0.0.1:5678 --wait-for-client your_script.py arg1
python -m debugpy --listen 127.0.0.1:5678 --wait-for-client -m your.module
```

### Pattern C: Attach to already-running process
```bash
python -m debugpy --listen 127.0.0.1:5678 --pid <pid>
```
Needs debugpy preinstalled in target's environment. Some kernels block ptrace injection (`/proc/sys/kernel/yama/ptrace_scope`). Fix: `echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope`.

### Remote-pdb (cleanest terminal agent option)
```bash
pip install remote-pdb
```
```python
from remote_pdb import set_trace
set_trace(host="127.0.0.1", port=4444)
```
Then: `nc 127.0.0.1 4444` — get a `(Pdb)` prompt exactly as if debugging locally.

## Connecting Clients

### Option 1: DAP client script
A tiny Python script that speaks DAP protocol over socket. Fine for automation, painful as interactive UX.

### Option 2: VS Code / Cursor / Zed
Add `launch.json`:
```json
{
  "name": "Attach to Process",
  "type": "debugpy",
  "request": "attach",
  "connect": { "host": "127.0.0.1", "port": 5678 },
  "justMyCode": false
}
```

### Option 3: remote-pdb (recommended for agents)
Use `remote-pdb` with `set_trace()` + `nc` connection. Cleanest agent-friendly choice.

## Debugging Hermes-Specific Processes

### Tests
Always add `-p no:xdist` or run single tests without xdist. `scripts/run_tests.sh` uses xdist by default and pdb does NOT work under it.

### run_agent.py / CLI
Add `breakpoint()` near the suspect line, run `hermes` normally.

### tui_gateway subprocess
**A. Source-edit the gateway:**
```python
# tui_gateway/server.py near top of serve()
import debugpy
debugpy.listen(("127.0.0.1", 5678))
debugpy.wait_for_client()
```
Start `hermes --tui`. TUI appears frozen (backend waiting). Attach client; execution resumes on `continue`.

**B. remote-pdb at specific handler:**
```python
from remote_pdb import set_trace
set_trace(host="127.0.0.1", port=4444)
```
Trigger the matching slash command, then `nc 127.0.0.1 4444`.

### _SlashWorker subprocess
Same pattern — `remote-pdb` with `set_trace()` inside the worker's exec path.

### Gateway (gateway/run.py)
Long-lived. Use `remote-pdb` at a handler, or `debugpy` with `--wait-for-client` if restarting anyway.

## Advanced Recipes

### Post-mortem wrapper for a whole script
```bash
python -m pdb -c continue script.py
# On crash, pdb lands at the frame of the exception with full locals
```

### Global exception hook in REPL/Jupyter
```python
import sys
def excepthook(etype, value, tb):
    import pdb; pdb.post_mortem(tb)
sys.excepthook = excepthook
```

### Async handler deadlock investigation
```python
from remote_pdb import set_trace
set_trace(host="127.0.0.1", port=4444)
# Trigger handler, then: nc 127.0.0.1 4444
# w to see suspended frame
# !import asyncio; asyncio.all_tasks() to see pending tasks
```

### Post-mortem on crash in subprocess
```bash
PYTHONFAULTHANDLER=1 python -m pdb -c continue path/to/entrypoint.py
```

## Complete pdb Command Reference

| Command | Action |
|---------|--------|
| `h` / `h cmd` | help |
| `n` | next line (step over) |
| `s` | step into |
| `r` | return from current function |
| `c` | continue |
| `unt N` | continue until line N |
| `j N` | jump to line N (same function only) |
| `l` / `ll` | list source around current line / full function |
| `w` | where (stack trace) |
| `u` / `d` | move up / down in the stack |
| `a` | print args of the current function |
| `p expr` / `pp expr` | print / pretty-print expression |
| `display expr` | auto-print expr on every stop |
| `b file:line` | set breakpoint |
| `b func` | break on function entry |
| `b file:line, cond` | conditional breakpoint |
| `cl N` | clear breakpoint N |
| `tbreak file:line` | one-shot breakpoint |
| `!stmt` | execute arbitrary Python |
| `interact` | full Python REPL in current scope (Ctrl+D to exit) |
| `q` | quit |

## Pitfalls

1. **pdb under pytest-xdist silently does nothing.** Use `-p no:xdist` or `-n 0`.
2. **`breakpoint()` in CI / non-TTY hangs.** Safe locally; never commit. Pre-commit grep: `rg -n 'breakpoint\(\)' --type py`
3. **`PYTHONBREAKPOINT=0`** disables all breakpoints.
4. **`debugpy.listen` blocks only with `wait_for_client()`.** Without it, execution continues.
5. **Attach to PID fails on hardened kernels.** `ptrace_scope=1` (Ubuntu default). Fix: `echo 0 > /proc/sys/kernel/yama/ptrace_scope`.
6. **Threads.** pdb only debugs current thread. Use debugpy for multithreaded code.
7. **asyncio.** pdb works in coroutines but `await` inside pdb needs Python 3.13+.
8. **`scripts/run_tests.sh` strips credentials and sets `HOME=<tmpdir>`.** Debug with raw pytest first.
9. **Forking / multiprocessing.** pdb doesn't follow forks. Each child needs own breakpoint.

## Verification Checklist

- [ ] After `pip install debugpy`: `python -c "import debugpy; print(debugpy.__version__)"`
- [ ] For remote debug: `ss -tlnp | grep 5678` confirms port listening
- [ ] First breakpoint actually hits
- [ ] `where` / `w` shows expected call stack
- [ ] Post-debug cleanup: no stray `breakpoint()` / `set_trace()` in committed code: `rg -n 'breakpoint\(\)|set_trace\(|debugpy\.listen' --type py`
