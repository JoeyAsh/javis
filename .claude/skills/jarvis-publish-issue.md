---
name: jarvis-publish-issue
description: Publish a JARVIS feature spec as a GitHub issue on JoeyAsh/javis, label `feature`, and add it to project PVT_kwHOAvcf5s4BVEuO with status Backlog. Returns the issue URL.
---

# JARVIS publish-issue skill

## When to use
Invoked by the orchestrator after `feature-planner` returns a spec body + `READY FOR AUTHORIZATION`. The orchestrator passes the title slug + spec body; this skill creates the GitHub issue, applies the `feature` label, adds to the project board in `Backlog`, and returns the issue URL.

## Inputs
- `<title>` — short kebab-case slug, used as `feat: <slug>` for the issue title (e.g., `wake-word-sensitivity-slider`).
- `<body>` — the verbatim spec body (Markdown). The skill MUST publish it byte-identical — no reformatting, no summarizing.

## Steps
Concrete bash commands the orchestrator runs:

```bash
# 1. Create issue, capture number
ISSUE_URL=$(gh issue create --repo JoeyAsh/javis \
  --title "feat: <title>" \
  --body-file <body-file-path> \
  --label feature)
echo "$ISSUE_URL"

# 2. Get issue node ID for project mutation
ISSUE_NODE_ID=$(gh api "repos/JoeyAsh/javis/issues/$(basename $ISSUE_URL)" --jq '.node_id')

# 3. Add to project, capture item ID
ITEM_ID=$(gh api graphql -f query='mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c}){item{id}}}' \
  -f p='PVT_kwHOAvcf5s4BVEuO' -f c="$ISSUE_NODE_ID" --jq '.data.addProjectV2ItemById.item.id')

# 4. Set status to Backlog
gh api graphql -f query='mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){updateProjectV2ItemFieldValue(input:{projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){projectV2Item{id}}}' \
  -f p='PVT_kwHOAvcf5s4BVEuO' -f i="$ITEM_ID" -f f='PVTSSF_lAHOAvcf5s4BVEuOzhQi_R8' -f o='c8f6649d'
```

## Important
- `--body-file` is mandatory — passing the body inline truncates at shell limits and breaks Markdown. Write the spec to a temp file (`mktemp`) and reference it.
- Publish the body verbatim. Do not let the orchestrator (or any subagent) reformat the spec.
- Returns the issue URL on stdout. The orchestrator surfaces it to the user.
