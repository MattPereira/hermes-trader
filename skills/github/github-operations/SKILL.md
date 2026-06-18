---
name: github-operations
description: "Complete GitHub workflow: auth, repos, issues, PRs, code review, codebase inspection. All via gh CLI or git+curl fallback."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Authentication, Repositories, Issues, Pull-Requests, Code-Review, CI/CD, Git, gh-cli]
    related_skills: [requesting-code-review, simplify-code]
---

# GitHub Operations

Single reference for all GitHub workflows: authentication, repository management, issues, pull requests, code review, and codebase inspection. Every section shows `gh` CLI first, then `git` + `curl` fallback.

## Shared Setup (used by all sections)

### Auth Detection

Run this once at the start of any GitHub workflow:
### Auth Detection

Run this once at the start of any GitHub workflow:

```bash
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  AUTH="gh"
else
  AUTH="git"
  if [ -z "$GITHUB_TOKEN" ]; then
    if _hermes_env="${HERMES_HOME:-$HOME/.hermes}/.env"; [ -f "$_hermes_env" ] && grep -q "^GITHUB_TOKEN=" "$_hermes_env"; then
      GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" "$_hermes_env" | head -1 | cut -d= -f2 | tr -d '\n\r')
    elif grep -q "github.com" ~/.git-credentials 2>/dev/null; then
      GITHUB_TOKEN=$(grep "github.com" ~/.git-credentials 2>/dev/null | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|')
    fi
  fi
fi
echo "Using: $AUTH"
```

For a reusable script, see `scripts/gh-env.sh`.

### Extracting Owner/Repo

```bash
REMOTE_URL=$(git remote get-url origin)
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)
```

---

## Section 1: Authentication

Setup authentication so the agent can work with GitHub. See `references/authentication-detailed.md` for the full guide.

### Decision tree

1. `gh auth status` shows authenticated → use `gh` for everything
2. `gh` installed but not authenticated → `gh auth login` or token-based
3. No `gh` → git-only method (HTTPS token or SSH key)

### gh CLI auth (recommended)

```bash
# Interactive (desktop)
gh auth login

# Token-based (headless)
echo "$GITHUB_TOKEN" | gh auth login --with-token
gh auth setup-git

# Verify
gh auth status
```

### Git-only: HTTPS token

```bash
git config --global credential.helper store
# Then do any git operation — enter username + token as password
git ls-remote https://github.com/<user>/<repo>.git
```

### Git-only: SSH key

```bash
ssh-keygen -t ed25519 -C "email@example.com" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub  # Add to https://github.com/settings/keys
ssh -T git@github.com
```

### API access without gh

```bash
export GITHUB_TOKEN="<token>"
curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

### Pitfalls

- **`$HERMES_HOME/.env`** not `~/.hermes/.env` — profile-aware paths matter
- Secret redaction masks tokens in output — `source` the file instead of reading it
- `gh auth login --with-token` needs stdin piping; empty var = device-code fallback

---

## Section 2: Repository Management

Create, clone, fork, configure, and manage repositories. Full API cheatsheet at `references/github-api-cheatsheet.md`.

### Clone

```bash
git clone https://github.com/owner/repo.git
git clone --depth 1 https://github.com/owner/repo.git  # shallow
gh repo clone owner/repo
```

### Create

```bash
gh repo create my-project --public --clone
gh repo create my-project --source . --public --push  # from existing dir

# curl fallback
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user/repos \
  -d '{"name":"my-project","private":false,"auto_init":true}'
```

### Fork and sync

```bash
gh repo fork owner/repo --clone
# Sync: git fetch upstream && git checkout main && git merge upstream/main && git push
gh repo sync $GH_USER/repo
```

### Settings and branch protection

```bash
gh repo edit --description "Updated" --visibility public
gh repo edit --enable-auto-merge
# Branch protection via curl — see references/github-api-cheatsheet.md
```

### Secrets (GitHub Actions)

```bash
gh secret set API_KEY --body "value"
gh secret list
# curl fallback requires encryption — use gh for secrets
```

### Releases

```bash
gh release create v1.0.0 --title "v1.0.0" --generate-notes
gh release create v1.0.0 ./dist/binary --notes "Release notes"
gh release list
```

### GitHub Actions

```bash
gh workflow list
gh run list --limit 10
gh run view <RUN_ID> --log-failed
gh run rerun <RUN_ID> --failed
gh workflow run ci.yml --ref main
```

---

## Section 3: Issues Management

Create, search, triage, and manage issues. Templates at `templates/bug-report.md` and `templates/feature-request.md`.

### View and search

```bash
gh issue list --state open --label "bug"
gh issue view 42
gh issue list --search "authentication error" --state all
```

### Create

```bash
gh issue create --title "Login redirect broken" \
  --body "## Steps to Reproduce\n1. ...\n" \
  --label "bug,backend" --assignee "username"
```

### Manage

```bash
gh issue edit 42 --add-label "priority:high"
gh issue edit 42 --add-assignee @me
gh issue comment 42 --body "Investigating..."
gh issue close 42 --reason "completed"
gh issue reopen 42
```

### Triage workflow

1. List untriaged: `gh issue list --label "needs-triage"`
2. Read and categorize each issue
3. Apply labels and priority
4. Assign if owner is clear
5. Comment with triage notes if needed

### Bulk operations

```bash
gh issue list --label "wontfix" --json number --jq '.[].number' | \
  xargs -I {} gh issue close {} --reason "not planned"
```

### curl fallback pattern

```bash
# List open issues
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/issues?state=open" | \
  python3 -c "import sys,json; [print(f'#{i[\"number\"]} {i[\"title\"]}') for i in json.load(sys.stdin) if 'pull_request' not in i]"
```

---

## Section 4: Pull Request Workflow

Full PR lifecycle: branch → commit → push → create → CI → merge. CI troubleshooting at `references/ci-troubleshooting.md`. Commit conventions at `references/conventional-commits.md`. PR body templates at `templates/pr-body-bugfix.md` and `templates/pr-body-feature.md`.

### Branch and commit

```bash
git checkout main && git pull origin main
git checkout -b feat/add-auth
# ... make changes ...
git add src/auth.py tests/test_auth.py
git commit -m "feat: add JWT-based authentication"
```

### Push and create PR

```bash
git push -u origin HEAD

gh pr create --title "feat: add JWT auth" \
  --body "## Summary\n- Adds login endpoints\nCloses #42"

# curl fallback
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls \
  -d '{"title":"feat: add JWT auth","body":"Closes #42","head":"feat/add-auth","base":"main"}'
```

### Monitor CI

```bash
gh pr checks --watch  # polls until done

# curl fallback: poll commit status
SHA=$(git rev-parse HEAD)
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/status
```

### Auto-fix CI failures

1. `gh run list --branch $(git branch --show-current)`
2. `gh run view <RUN_ID> --log-failed`
3. Fix code, `git push`, re-check (up to 3 attempts)

### Merge

```bash
gh pr merge --squash --delete-branch
gh pr merge --auto --squash --delete-branch  # when checks pass
```

---

## Section 5: Code Review

Review local changes (pre-push) or PRs on GitHub. Review output template at `references/review-output-template.md`.

### Review local changes

```bash
git diff main...HEAD --stat        # scope
git diff main...HEAD               # full diff
git diff main...HEAD -- src/auth.py  # single file

# Check for issues
git diff main...HEAD | grep -n "print\|console\.log\|TODO\|FIXME"
git diff main...HEAD | grep -in "password\|secret\|api_key"
```

### Review output format

```
## Code Review Summary
### Critical
- **file:line** — issue description. Suggestion: fix.
### Warnings
- **file:line** — issue description.
### Suggestions
- **file:line** — improvement idea.
### Looks Good
- What works well.
```

### Review a PR on GitHub

```bash
# View
gh pr view 123
gh pr diff 123

# Check out locally
git fetch origin pull/123/head:pr-123
git checkout pr-123

# Leave comments
gh pr comment 123 --body "Overall looks good."
gh pr review 123 --approve --body "LGTM!"
gh pr review 123 --request-changes --body "See inline comments."
```

### Review checklist

- **Correctness**: Does it do what it claims? Edge cases?
- **Security**: No hardcoded secrets, input validation, no SQL injection/XSS
- **Quality**: Clear naming, DRY, single responsibility
- **Testing**: New code paths tested? Happy + error paths?
- **Performance**: No N+1 queries, appropriate caching
- **Documentation**: Public APIs documented, non-obvious logic explained

---

## Section 6: Codebase Inspection

Analyze repos for LOC, language breakdown, and code-vs-comment ratios using `pygount`.

```bash
pip install pygount 2>/dev/null

# Summary (always exclude deps)
pygount --format=summary --folders-to-skip=".git,node_modules,venv,.venv,__pycache__,dist,build" .

# Filter by language
pygount --suffix=py --format=summary .

# JSON output
pygount --format=json .
```

### Pitfalls

- Always use `--folders-to-skip` — otherwise pygount crawls deps and hangs
- Markdown shows 0 code lines (all classified as comments)
- For large monorepos, use `--suffix` to target specific languages

---

## Quick Reference

| Action | gh | git + curl |
|--------|-----|-----------|
| Clone | `gh repo clone o/r` | `git clone URL` |
| Create repo | `gh repo create name` | `curl POST /user/repos` |
| List issues | `gh issue list` | `curl GET /repos/o/r/issues` |
| Create issue | `gh issue create` | `curl POST /repos/o/r/issues` |
| Create PR | `gh pr create` | `curl POST /repos/o/r/pulls` |
| Merge PR | `gh pr merge --squash` | `curl PUT /repos/o/r/pulls/N/merge` |
| Review PR | `gh pr review N --approve` | `curl POST /repos/o/r/pulls/N/reviews` |
| Check CI | `gh pr checks` | `curl GET /repos/o/r/commits/SHA/status` |
| Create release | `gh release create v1.0` | `curl POST /repos/o/r/releases` |
| Set secret | `gh secret set KEY` | `curl PUT /repos/o/r/actions/secrets/KEY` |
