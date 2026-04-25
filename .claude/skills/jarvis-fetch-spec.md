---
name: jarvis-fetch-spec
description: Fetch a JARVIS feature spec from a GitHub issue on JoeyAsh/javis. Returns the issue body (Markdown spec) on stdout. Used by backend-dev, frontend-dev, tester, and reviewer to load the spec they're implementing/testing/reviewing against.
---

# JARVIS fetch-spec skill

## When to use

Invoked by any dev / test / review agent at the start of their turn to load the feature spec body. Centralizes the `gh` command so all agents stay in sync if the repo or query changes.

## Inputs

- `<issue>` — issue URL (e.g., `https://github.com/JoeyAsh/javis/issues/42`) or just the number (e.g., `42`).

## Output

The spec body (Markdown) on stdout. The agent reads it from there.

## Steps

```bash
# Body only (most common — pass to dev / test / review agent)
gh issue view <issue> --repo JoeyAsh/javis --json body --jq '.body'

# Body + title + number (for the orchestrator when it needs the issue title or number)
gh issue view <issue> --repo JoeyAsh/javis --json body,title,number
```

## Important

- Always pass `--repo JoeyAsh/javis` explicitly. Do not rely on the cwd's git remote — agents may run from temporary worktrees.
- The issue body is the canonical source of the spec. The dev / test / review agents work against it, not against any local file.
