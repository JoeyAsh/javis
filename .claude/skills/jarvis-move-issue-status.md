---
name: jarvis-move-issue-status
description: Transition a JARVIS GitHub issue's project-board status (Backlog → Ready → Todo → In Progress → In Review → Blocked → Done) via GraphQL.
---

# JARVIS move-issue-status skill

## When to use
Orchestrator calls this when transitioning an issue (e.g., before starting implementation: `In Progress`; after `reviewer` returns `PASS`: `Done`; if blocked: `Blocked`).

## Inputs
- `<issue-number>` — issue number on `JoeyAsh/javis`.
- `<status>` — one of `Backlog | Ready | Todo | In Progress | In Review | Blocked | Done`.

## Steps

```bash
# 1. Resolve status name → option ID
case "<status>" in
  Backlog)      OPT='c8f6649d' ;;
  Ready)        OPT='de418b82' ;;
  Todo)         OPT='9c58e8bc' ;;
  "In Progress") OPT='cc34a6c9' ;;
  "In Review")  OPT='11f92f6f' ;;
  Blocked)      OPT='de3248d3' ;;
  Done)         OPT='eeaaf043' ;;
  *) echo "ERROR: unknown status '<status>'" >&2; exit 1 ;;
esac

# 2. Get issue node ID
NODE_ID=$(gh api "repos/JoeyAsh/javis/issues/<issue-number>" --jq '.node_id')

# 3. Find project item ID for this issue
ITEM_ID=$(gh api graphql -f query='query($n:ID!){node(id:$n){... on Issue{projectItems(first:10){nodes{id project{id}}}}}}' \
  -f n="$NODE_ID" --jq '.data.node.projectItems.nodes[] | select(.project.id=="PVT_kwHOAvcf5s4BVEuO") | .id')

# 4. Update status
gh api graphql -f query='mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){updateProjectV2ItemFieldValue(input:{projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){projectV2Item{id}}}' \
  -f p='PVT_kwHOAvcf5s4BVEuO' -f i="$ITEM_ID" -f f='PVTSSF_lAHOAvcf5s4BVEuOzhQi_R8' -f o="$OPT"
```

## Important
Status names are case-sensitive ("In Progress", not "in-progress"). On unknown status, the skill exits with an error.
