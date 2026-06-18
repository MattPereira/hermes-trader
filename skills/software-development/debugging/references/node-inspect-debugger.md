# Node.js Debugging Deep Reference

Extended reference for Node.js debugging with `node inspect` and Chrome DevTools Protocol. For the quick reference and methodology, see the main `debugging` skill.

## Programmatic CDP (Scripting from Terminal)

For automated breakpoints, scope capture, and repro scripting, use `chrome-remote-interface`:

```bash
npm i -g chrome-remote-interface
node --inspect-brk=9229 target.js &
```

Driver script (`/tmp/cdp-debug.js`):
```javascript
const CDP = require('chrome-remote-interface');

(async () => {
  const client = await CDP({ port: 9229 });
  const { Debugger, Runtime } = client;

  Debugger.paused(async ({ callFrames, reason }) => {
    const top = callFrames[0];
    console.log(`PAUSED: ${reason} @ ${top.url}:${top.location.lineNumber + 1}`);

    // Walk scopes for locals
    for (const scope of top.scopeChain) {
      if (scope.type === 'local' || scope.type === 'closure') {
        const { result } = await Runtime.getProperties({
          objectId: scope.object.objectId,
          ownProperties: true,
        });
        for (const p of result) {
          console.log(`  ${scope.type}.${p.name} =`, p.value?.value ?? p.value?.description);
        }
      }
    }

    // Evaluate expression in paused frame
    const { result } = await Debugger.evaluateOnCallFrame({
      callFrameId: top.callFrameId,
      expression: 'typeof state !== "undefined" ? JSON.stringify(state) : "n/a"',
    });
    console.log('state =', result.value ?? result.description);

    await Debugger.resume();
  });

  await Runtime.enable();
  await Debugger.enable();

  await Debugger.setBreakpointByUrl({
    urlRegex: '.*app\\.tsx$',
    lineNumber: 119,  // 0-indexed
    columnNumber: 0,
  });

  await Runtime.runIfWaitingForDebugger();
})();
```

Run: `node /tmp/cdp-debug.js`

Install to throwaway location if you don't want to dirty the project:
```bash
mkdir -p /tmp/cdp-tools && cd /tmp/cdp-tools && npm i chrome-remote-interface
NODE_PATH=/tmp/cdp-tools/node_modules node /tmp/cdp-debug.js
```

## Debugging Hermes ui-tui

### Single Ink component under dev
```bash
cd ui-tui
npm run build
node --inspect-brk dist/entry.js
# In another terminal:
node inspect -p <node pid>
# debug> sb('dist/app.js', 220)
# debug> cont
# repl → inspect props, state refs, useInput handler values
```

### Running hermes --tui
```bash
hermes --tui &
TUI_PID=$(pgrep -f 'ui-tui/dist/entry' | head -1)
kill -SIGUSR1 "$TUI_PID"
curl -s http://127.0.0.1:9229/json/list | jq -r '.[0].webSocketDebuggerUrl'
node inspect ws://127.0.0.1:9229/<uuid>
```

### _SlashWorker / PTY child processes
Those are Python — use `python-debugpy` reference. Only Node portions (Ink UI, tui_gateway client, tsx-run tests) use this skill.

## Vitest Tests Under Debugger

```bash
cd ui-tui
node --inspect-brk ./node_modules/vitest/vitest.mjs run --no-file-parallelism src/app/foo.test.tsx
# In another terminal: node inspect -p <pid>, then sb('src/app/foo.tsx', 42), cont
```

Use `--no-file-parallelism` (vitest) or `--runInBand` (jest) so only one worker exists.

## Heap Snapshots & CPU Profiles

### CPU profile (5 seconds)
```javascript
await client.Profiler.enable();
await client.Profiler.start();
await new Promise(r => setTimeout(r, 5000));
const { profile } = await client.Profiler.stop();
require('fs').writeFileSync('/tmp/cpu.cpuprofile', JSON.stringify(profile));
// Open in Chrome DevTools → Performance tab
```

### Heap snapshot
```javascript
await client.HeapProfiler.enable();
const chunks = [];
client.HeapProfiler.addHeapSnapshotChunk(({ chunk }) => chunks.push(chunk));
await client.HeapProfiler.takeHeapSnapshot({ reportProgress: false });
require('fs').writeFileSync('/tmp/heap.heapsnapshot', chunks.join(''));
```

## TypeScript Source Maps

Breakpoints hit emitted JS, not `.ts`. Options:
- Break in built `dist/*.js`
- Enable sourcemaps: `node --enable-source-maps` + `sb('src/app.tsx', N)` — but only with CDP clients that follow sourcemaps. `node inspect` CLI does NOT.

## Pitfalls

1. **`--inspect` vs `--inspect-brk`.** Without `-brk`, script races past your first breakpoint.
2. **Port collisions.** Default 9229. Use `--inspect=0` for random port. Read from `/json/list`.
3. **Child processes.** `--inspect` on parent does NOT inspect children. Use `NODE_OPTIONS='--inspect-brk'` to propagate.
4. **Background kills.** Ctrl+C out of `node inspect` while target is paused → target stays paused. `cont` first or kill explicitly.
5. **Running `node inspect` through agent terminal.** PTY-friendly REPL. Use `terminal(pty=true)` or `background=true` + `process(action='submit')`.
6. **Security.** `--inspect=0.0.0.0:9229` exposes arbitrary code execution. Always bind to 127.0.0.1.

## Verification Checklist

- [ ] `curl -s http://127.0.0.1:9229/json/list` returns exactly the expected target
- [ ] First breakpoint actually hits (if not, missed `--inspect-brk` or attached after execution completed)
- [ ] Source listing at pause shows right file (mismatch = sourcemap issue)
- [ ] `exec process.pid` in `repl` returns expected PID
