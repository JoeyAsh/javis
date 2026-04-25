---
name: jarvis-issue-status
description: Quick health-check of the JARVIS GitHub project board — list issues grouped by status (Backlog / Ready / Todo / In Progress / In Review / Blocked / Done). Use at session start or when planning the next batch.
---

# JARVIS issue-status skill

## When to use

- Session start, to see what's open and what's mid-flight.
- Before invoking `feature-planner`, to verify the planned feature isn't already an open issue.
- When asked "what's the project state right now?".

## Steps

```bash
# 1. List all issues with their project status
gh api graphql -f query='
{
  repository(owner: "JoeyAsh", name: "javis") {
    issues(states: OPEN, first: 100) {
      nodes {
        number
        title
        url
        projectItems(first: 5) {
          nodes {
            project { id title }
            fieldValueByName(name: "Status") {
              ... on ProjectV2ItemFieldSingleSelectValue { name }
            }
          }
        }
      }
    }
  }
}' --jq '.data.repository.issues.nodes[] |
  {n: .number, t: .title, s: (.projectItems.nodes[] | select(.project.id == "PVT_kwHOAvcf5s4BVEuO") | .fieldValueByName.name)}
  | "\(.s // "Unassigned")\t#\(.n)\t\(.t)"' \
  | sort

# 2. (optional) Closed-recently view for sanity check
gh issue list --repo JoeyAsh/javis --state closed --limit 10 \
  --json number,title,closedAt --template '{{range .}}#{{.number}} {{.title}} (closed {{.closedAt}}){{"\n"}}{{end}}'
```

## Output format

One line per open issue, `<status>\t#<num>\t<title>`, sorted by status. Then a small "recently closed" tail for context.

## Notes

Needs `gh auth status` healthy. If not authed, prompt user to run `gh auth login`.
