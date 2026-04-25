---
name: jarvis-brief-template
description: Produces a ready-to-paste delegation brief for frontend-dev or backend-dev that includes the MANDATORY RULES block and a 10-item Y/N self-check. Use this whenever the orchestrator is about to delegate a frontend task.
---

# JARVIS delegation brief template

When you use this skill, produce the following block as the **opening** of the brief you send to `frontend-dev` (or adapt as needed for `backend-dev`). Fill in the placeholder sections. Do NOT omit the MANDATORY RULES — they are the single most important guard against rule-violation slippage in this project.

---

## How to use

1. Start the brief with the verbatim MANDATORY RULES block below.
2. Fill in the Context, Scope, and Verification sections with your task specifics.
3. End the brief with the verbatim Self-Check block. The agent must answer Y/N for every item at the end of its return message.

---

## Brief template (copy-paste)

```markdown
## MANDATORY RULES (re-read before every file you write — each rule is a hard failure mode)

[Copy the entire "MANDATORY RULES" block verbatim from `.claude/agents/frontend-dev.md` (the 12 numbered rules). It is the single source of truth — do NOT paraphrase or reorder. If the block is missing rules or has been edited, fix `frontend-dev.md` instead of this brief.]

## Context

[SPEC URL or INLINE REQUIREMENTS]

[UPSTREAM DECISIONS — previous batches / commits this builds on]

## Scope

[STEP — what this batch delivers, bullet list]

[FILES TO TOUCH — explicit paths]

[FILES NOT TO TOUCH — explicit paths]

## Verification

- `npx tsc --noEmit` → 0 errors
- `npm run build` → success, main chunk ≤ 90 KB, ThreeOrb chunk lazy
- `npm run test` → 0 failing
- [any feature-specific acceptance criteria]

## Self-check (answer Y/N verbatim at end of your return message)

1. Props + object-shape types use `interface` (not `type`)? Y/N
2. Zero type/interface/enum declarations in `.tsx` or hook `.ts` files? Y/N
3. Zero top-level non-component functions/consts (helpers) in `.tsx` files? Y/N
4. Module-level constants in `.tsx`: only component-local lookup tables; zero numeric thresholds / timeouts / cross-component values? Y/N
5. Zero multi-component files (one `function Foo` / `const Foo: FC =` per file)? Y/N
6. Tailwind used first; every surviving `.module.css` has a justification comment? Y/N
7. Zero `fetch()` / `axios` / `new WebSocket()` outside exempt paths? Y/N
8. Zero global `import './*.css'` in component files? Y/N
9. Zero inline styles except CSS-var injection / runtime-computed dynamics? Y/N
10. Named + default export on every component? Y/N
11. Zero `any` / `!` / `@ts-ignore`? Y/N
12. `@ui/orb/orbEngine.ts` untouched? Y/N

If any answer is N, STOP and fix it before returning.
```

---

## When NOT to use this skill

- Trivial one-liner changes (rename, typo fix) — the overhead exceeds the value.
- Backend-only tasks — consider a separate `backend-dev` brief template (not yet created).
- Documentation-only changes under `docs/`.

## Rationale

This skill exists because delegation briefs without the verbatim MANDATORY RULES block were observed to produce rule-violating code even when `CLAUDE.md` documented every rule. Agents treat the brief as the source of truth — if the rules are not in the brief, they get ignored. Embedding the block here guarantees they cannot be forgotten.
