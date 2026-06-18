# Authoring In-Repo Skills

There are two places a SKILL.md can live:

1. **User-local:** `~/.hermes/skills/<category>/<name>/SKILL.md` — created via `skill_manage(action='create')`
2. **In-repo:** `<hermes-agent-repo>/skills/<category>/<name>/SKILL.md` — committed, shipped with the package. Use `write_file` + `git add`

## Required Frontmatter

Source of truth: `tools/skill_manager_tool.py::_validate_frontmatter`

- Starts with `---` as the first bytes (no leading blank line)
- Closes with `\n---\n` before the body
- Parses as a YAML mapping
- `name` field present, ≤ 64 chars, lowercase + hyphens
- `description` field present, ≤ 1024 chars
- Non-empty body after closing `---`

```yaml
---
name: my-skill-name
description: Use when <trigger>. <one-line behavior>.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [short, descriptive, tags]
    related_skills: [other-skill, another-skill]
---
```

## Size Limits

- Description: ≤ 1024 chars (enforced)
- Full SKILL.md: ≤ 100,000 chars (~36k tokens)
- Peer skills sit at **8-14k chars**. If pushing past 20k, split into `references/*.md`

## Structure

```
# <Title>
## Overview (what and why)
## When to Use (triggers + counter-triggers)
## <Topic sections>
## Common Pitfalls
## Verification Checklist
```

## Pitfalls

1. **`skill_manage(action='create')` writes to `~/.hermes/skills/`**, not the repo tree. Use `write_file` for in-repo creation.
2. **Leading whitespace before `---`** fails validation.
3. **Description too generic.** Start with "Use when..." and describe the trigger class.
4. **Expecting the current session to see the new skill.** It won't — skill loader is cached at session start.
5. **Linking to skills that don't exist in-repo.** Prefer only in-repo links from in-repo skills.
