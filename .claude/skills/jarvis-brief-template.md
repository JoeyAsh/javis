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

1. **`interface` for Props and object-shape types.** `type FooProps = {...}` is a CRITICAL violation. Unions (`type OrbState = 'idle' | 'listening' | ...`), mapped types, and utility types stay `type`.
2. **Interfaces NEVER in `.tsx` or hook `.ts`** — always in a sibling `<Name>.types.ts`. Applies to helper-component Props within the same feature too.
3. **1 component per file — no exceptions.** Helpers ≥ 20 LOC get their own folder; helpers < 20 LOC get a sibling file. A second `function Foo` / `const Foo: FC =` in a parent `.tsx` is a CRITICAL violation.
4. **Tailwind FIRST.** `.module.css` ONLY for `@keyframes`, `mix-blend-mode`, `radial/conic-gradient` with custom stops, `backdrop-filter` with ≥ 2 layers, complex `mask` / `clip-path`. Every `.module.css` needs a top comment justifying why Tailwind cannot express it.
5. **NO `fetch()` / `axios` / `new WebSocket()`** outside `@core/api/*` (RTK Query) and `@core/websocket/wsClient.ts`. The `fetch('/sounds/...')` in `@core/audio/audioEngine.ts` is the only other exempt pattern.
6. **NO global `import './*.css'`** in component files. Aggregated global CSS imported once from a library barrel (e.g. `@ui/components.css`) is acceptable.
7. **No inline styles** except CSS custom-property injection (`style={{ '--foo': value }}`) and runtime-computed dynamics Tailwind cannot express.
8. **Named + default export** on every component.
9. **Strict TypeScript**: no `any`, no `!`, no `@ts-ignore`.
10. **"Port" / "migrate" NEVER means byte-for-byte copy.** Apply rules 1–9 to the legacy while preserving behavior.

---

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
2. Zero interfaces in `.tsx` / hook `.ts` files? Y/N
3. Zero multi-component files (one `function Foo` / `const Foo: FC =` per file)? Y/N
4. Tailwind used first; every surviving `.module.css` has a justification comment? Y/N
5. Zero `fetch()` / `axios` / `new WebSocket()` outside exempt paths? Y/N
6. Zero global `import './*.css'` in component files? Y/N
7. Zero inline styles except CSS-var injection / runtime-computed dynamics? Y/N
8. Named + default export on every component? Y/N
9. Zero `any` / `!` / `@ts-ignore`? Y/N
10. `@ui/orb/orbEngine.ts` untouched? Y/N

If any answer is N, STOP and fix it before returning.
```

---

## When NOT to use this skill

- Trivial one-liner changes (rename, typo fix) — the overhead exceeds the value.
- Backend-only tasks — consider a separate `backend-dev` brief template (not yet created).
- Documentation-only changes under `docs/`.

## Rationale

This skill exists because delegation briefs without the verbatim MANDATORY RULES block were observed to produce rule-violating code even when `CLAUDE.md` documented every rule. Agents treat the brief as the source of truth — if the rules are not in the brief, they get ignored. Embedding the block here guarantees they cannot be forgotten.
