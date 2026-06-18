# Claude Code Complete Reference

Full CLI reference for Claude Code v2.x. For the quick orchestration guide, see the main `coding-agents` skill.

## All CLI Flags

### Session & Environment
| Flag | Effect |
|------|--------|
| `-p, --print` | Non-interactive one-shot mode |
| `-c, --continue` | Resume most recent conversation in current directory |
| `-r, --resume <id>` | Resume specific session |
| `--fork-session` | Create new session ID when resuming |
| `--session-id <uuid>` | Use specific UUID |
| `--no-session-persistence` | Don't save session to disk |
| `--add-dir <paths...>` | Grant access to additional directories |
| `-w, --worktree [name]` | Isolated git worktree |
| `--tmux` | Create tmux session for worktree |
| `--from-pr [number]` | Resume session linked to PR |

### Model & Performance
| Flag | Effect |
|------|--------|
| `--model <alias>` | sonnet, opus, haiku, or full name |
| `--effort <level>` | low, medium, high, max, auto |
| `--max-turns <n>` | Limit agentic loops (print mode) |
| `--max-budget-usd <n>` | Cap API spend |
| `--fallback-model <model>` | Auto-fallback on overload |

### Permission & Safety
| Flag | Effect |
|------|--------|
| `--dangerously-skip-permissions` | Auto-approve ALL tool use |
| `--permission-mode <mode>` | default, acceptEdits, plan, auto, dontAsk, bypassPermissions |
| `--allowedTools <tools...>` | Whitelist tools |
| `--disallowedTools <tools...>` | Blacklist tools |

### Output & Input Format
| Flag | Effect |
|------|--------|
| `--output-format <fmt>` | text, json, stream-json |
| `--input-format <fmt>` | text, stream-json |
| `--json-schema <schema>` | Force structured JSON output |
| `--verbose` | Full turn-by-turn output |
| `--include-partial-messages` | Include partial chunks (stream-json) |

### System Prompt & Context
| Flag | Effect |
|------|--------|
| `--append-system-prompt <text>` | Add to default system prompt |
| `--system-prompt <text>` | Replace entire system prompt |
| `--bare` | Skip hooks, plugins, MCP, CLAUDE.md |
| `--agents '<json>'` | Define custom subagents |
| `--mcp-config <path>` | Load MCP servers from JSON |
| `--settings <file-or-json>` | Load additional settings |

### Tool Name Syntax
```
Read                    # All file reading
Edit                    # File editing
Write                   # File creation
Bash                    # All shell commands
Bash(git *)             # Only git commands
Bash(git commit *)      # Only git commit commands
mcp__<server>__<tool>   # Specific MCP tool
```

## Interactive Slash Commands

### Session
| Command | Purpose |
|---------|---------|
| `/compact [focus]` | Compress context |
| `/clear` | Fresh start |
| `/context` | Visualize context usage |
| `/cost` | Token usage breakdown |
| `/resume` | Switch session |
| `/rewind` | Revert to checkpoint |
| `/btw <question>` | Side question without context cost |

### Development
| Command | Purpose |
|---------|---------|
| `/review` | Code review of current changes |
| `/security-review` | Security analysis |
| `/plan [description]` | Enter plan mode |
| `/batch` | Auto-create worktrees for parallel changes |

### Configuration
| Command | Purpose |
|---------|---------|
| `/model [model]` | Switch models |
| `/effort [level]` | Set reasoning effort |
| `/memory` | Open CLAUDE.md |
| `/permissions` | View/update tool permissions |
| `/voice` | Push-to-talk voice mode |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+C` | Cancel input or generation |
| `Ctrl+D` | Exit |
| `Ctrl+B` | Background a running task |
| `Ctrl+V` | Paste image |
| `Ctrl+O` | Transcript mode (see thinking) |
| `Shift+Tab` | Cycle permission modes |
| `Alt+P` | Switch model |
| `Alt+T` | Toggle thinking |

### Input Prefixes
| Prefix | Action |
|--------|--------|
| `!` | Execute bash directly |
| `@` | Reference files/dirs with autocomplete |
| `#` | Quick add to CLAUDE.md |

**Pro tip:** Use "ultrathink" in prompt for maximum reasoning effort.

## Settings Hierarchy (highest to lowest)
1. CLI flags
2. `.claude/settings.local.json` (personal, gitignored)
3. `.claude/settings.json` (shared, git-tracked)
4. `~/.claude/settings.json` (global)

## CLAUDE.md Hierarchy
1. `~/.claude/CLAUDE.md` — global
2. `./CLAUDE.md` — project-specific
3. `.claude/CLAUDE.local.md` — personal overrides

## Custom Subagents

Create `.claude/agents/<name>.md`:
```markdown
---
name: security-reviewer
description: Security-focused code review
model: opus
tools: [Read, Bash]
---
You are a senior security engineer. Review code for:
- Injection vulnerabilities
- Auth/authz flaws
- Secrets in code
```

Invoke: `@security-reviewer review the auth module`

## Hooks

Configure in `.claude/settings.json`:
```json
{
  "hooks": {
    "PostToolUse": [{"matcher": "Write(*.py)", "hooks": [{"type": "command", "command": "ruff check --fix $CLAUDE_FILE_PATHS"}]}],
    "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "if echo \"$CLAUDE_TOOL_INPUT\" | grep -q 'rm -rf'; then echo 'Blocked!' && exit 2; fi"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "echo 'Claude finished' >> /tmp/claude-activity.log"}]}]
  }
}
```

Hook types: UserPromptSubmit, PreToolUse, PostToolUse, Notification, Stop, SubagentStop, PreCompact, SessionStart.

## MCP Integration
```
claude mcp add -s user github -- npx @modelcontextprotocol/server-github
claude mcp add -s local postgres -- npx @anthropic-ai/server-postgres --connection-string postgresql://localhost/mydb
```

Scopes: `-s user` (global), `-s local` (project personal), `-s project` (project shared).

## Context Window Health
- **< 70%** — Normal operation
- **70-85%** — Precision drops, consider `/compact`
- **> 85%** — Hallucination risk spikes, use `/compact` or `/clear`

## Environment Variables
| Variable | Effect |
|----------|--------|
| `ANTHROPIC_API_KEY` | API key auth |
| `CLAUDE_CODE_EFFORT_LEVEL` | Default effort |
| `MAX_THINKING_TOKENS` | Cap thinking tokens (0 = disable) |
| `MAX_MCP_OUTPUT_TOKENS` | Cap MCP output (default varies) |

## Pitfalls
1. Interactive mode REQUIRES tmux — Claude Code is a full TUI app
2. `--dangerously-skip-permissions` dialog defaults to "No, exit" — must send Down then Enter
3. `--max-budget-usd` minimum is ~$0.05
4. `--max-turns` is print-mode only
5. Session resumption requires same directory
6. `--json-schema` needs enough `--max-turns`
7. Trust dialog only appears once per directory
8. Background tmux sessions persist — always clean up
9. `--bare` skips OAuth — requires `ANTHROPIC_API_KEY`
10. Context degradation is real — monitor with `/context`
