# GitHub Authentication — Detailed Guide

Complete authentication setup for GitHub: HTTPS tokens, SSH keys, gh CLI, and API access.

## Method 1: Git-Only (No gh, No sudo)

### Option A: HTTPS with Personal Access Token

**Step 1: Create token** at https://github.com/settings/tokens
- Scopes: `repo`, `workflow`, `read:org`
- Expiration: 90 days recommended

**Step 2: Configure git**
```bash
git config --global credential.helper store
# Do a test operation — enter username + token as password
git ls-remote https://github.com/<user>/<repo>.git
```

**Alternative: cache helper (8-hour memory)**
```bash
git config --global credential.helper 'cache --timeout=28800'
```

**Alternative: embed token in URL (per-repo)**
```bash
git remote set-url origin https://<username>:<token>@github.com/<owner>/<repo>.git
```

**Step 3: Configure identity**
```bash
git config --global user.name "Name"
git config --global user.email "email@example.com"
```

### Option B: SSH Key

```bash
# Check existing
ls -la ~/.ssh/id_*.pub 2>/dev/null

# Generate
ssh-keygen -t ed25519 -C "email@example.com" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub  # Add to https://github.com/settings/keys

# Test
ssh -T git@github.com

# Auto-rewrite HTTPS to SSH
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

## Method 2: gh CLI

```bash
# Interactive browser login
gh auth login

# Token-based (headless)
echo "$GITHUB_TOKEN" | gh auth login --with-token
gh auth setup-git

# Verify
gh auth status
```

## Using the GitHub API Without gh

```bash
export GITHUB_TOKEN=*** -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

Extract token from git credentials:
```bash
grep "github.com" ~/.git-credentials 2>/dev/null | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|'
```

## Detect Auth Method

```bash
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  echo "AUTH_METHOD=gh"
elif [ -n "$GITHUB_TOKEN" ]; then
  echo "AUTH_METHOD=curl"
elif [ -f "$HERMES_HOME/.env" ] && grep -q "^GITHUB_TOKEN=*** "$HERMES_HOME/.env"; then
  source "$HERMES_HOME/.env"
  echo "AUTH_METHOD=curl"
elif grep -q "github.com" ~/.git-credentials 2>/dev/null; then
  export GITHUB_TOKEN=$(grep "github.com" ~/.git-credentials | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|')
  echo "AUTH_METHOD=curl"
else
  echo "AUTH_METHOD=none"
fi
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `git push` asks for password | GitHub disabled password auth. Use token as password, or SSH |
| `Permission denied` | Token may lack `repo` scope — regenerate |
| `Authentication failed` | Stale credentials — `git credential reject` then re-auth |
| SSH connection refused | Try port 443: add `Host github.com` / `Port 443` / `Hostname ssh.github.com` to `~/.ssh/config` |
| Multiple accounts | Use SSH with different keys per host alias in `~/.ssh/config` |

## Pitfalls

- **Always use `$HERMES_HOME/.env`** not `~/.hermes/.env` — profile-aware paths
- **Secret redaction** masks tokens in output — `source` the file and use the variable
- **`--with-token` needs stdin** — empty var = device-code fallback
