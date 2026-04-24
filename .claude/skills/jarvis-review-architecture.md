---
name: jarvis-review-architecture
description: Runs a fixed sequence of ripgrep checks across frontend/src to detect rule violations (interface-vs-type, inline types, multi-component files, inline styles, global CSS, direct network calls, cross-feature imports, banned TS features). Produces a severity-grouped report ready for a dev agent to act on.
---

# JARVIS architecture review

Invoke this skill to sweep `frontend/src/` for violations of the project's architectural rules. Run each `rg` command verbatim from the repo root. Collect findings into a **Critical / Warning** grouped report.

All commands assume `rg` (ripgrep) is installed. If `grep -rn` is the only option, translate the regex using BRE/ERE as appropriate — semantics are the same.

---

## Run order

### 1. Props defined as `type` alias (Critical)

```bash
rg --type ts --type tsx -n "^(export\s+)?type\s+\w*Props\s*=" frontend/src
```

**Detects**: `type FooProps = {...}`. These must be `interface FooProps {...}` per rule 1.
**Fix**: Change `type FooProps =` to `interface FooProps` and convert `=` to nothing (no `=` in interface declaration). Unions and utility types are allowed to stay `type`; only Props / object-shape types are CRITICAL.

### 2. Type alias declared in `.tsx` (Critical)

```bash
rg --type tsx -n "^(export\s+)?type\s+\w" frontend/src --glob='!*__tests__*'
```

**Detects**: any `type Foo = ...` living in a `.tsx` file. All type declarations belong in sibling `<Name>.types.ts`.
**Fix**: Move the type into a sibling `.types.ts` file, import with `import type { Foo } from './<Name>.types';`.

### 3. Interface declared in `.tsx` (Critical)

```bash
rg --type tsx -n "^(export\s+)?interface\s+\w" frontend/src
```

**Detects**: any `interface Foo {...}` living in a `.tsx` file. Interfaces belong in sibling `<Name>.types.ts`.
**Fix**: Move the interface into a sibling `.types.ts` file, import with `import type { Foo } from './<Name>.types';`.

### 4. Interface declared in hook `.ts` (Critical)

```bash
rg -g 'hooks/*.ts' -g '!*.types.ts' -n "^(export\s+)?interface\s+\w" frontend/src
```

**Detects**: interfaces inline in hook implementation files.
**Fix**: Move to `<hook>.types.ts`.

### 5. Top-level helper functions in `.tsx` (Critical)

```bash
rg --type tsx -n "^(export\s+)?(function|const)\s+[a-z]\w*\s*[=(]" frontend/src --glob='!*__tests__*'
```

**Detects**: lowercase-start function or const declarations at module level in `.tsx` files — these are helpers, not components. Helper functions belong in sibling `utils.ts`.
**Fix**: Move to sibling `utils.ts` (or feature-level `utils.ts` if reused across multiple components). For shared utilities like `formatTime`, consolidate to `@common/utils/time.ts`.

### 6. Module-level constants in `.tsx` (Critical for thresholds/timeouts, allowed for lookup tables)

```bash
rg --type tsx -n "^(export\s+)?const\s+[A-Z_]+\s*=" frontend/src --glob='!*__tests__*'
```

**Detects**: UPPERCASE constants at module level in `.tsx` files. Classify each hit:

- **Allowed (not a violation)** — component-local style / config lookup tables bound to a single component: `VARIANT_CLASSES`, `SIZE_CLASSES`, `PARTICLE_CONFIGS`, `TICK_ANGLES`, `STROKE_COLOR`, `FILL_OPACITY`. Typically objects / arrays. Consumed only inside this one `.tsx`.
- **Critical violation** — numeric thresholds (`MIN_W = 180`), timeouts (`TIMEOUT_MS = 10_000`), cross-component values, feature flags, locale/tz constants. These belong in a sibling `constants.ts`.

**Fix**: Move Critical-class constants to `constants.ts`. Leave lookup tables in place. Rule of thumb: if the value is a number / time / used outside this component, extract it.

### 7. Multiple component declarations in one `.tsx` (Critical)

```bash
rg --type tsx -l "(export\s+)?(function|const)\s+[A-Z]\w*\s*[:=(][^{]*(ReactElement|JSX\.Element|ReactNode|FC\s*<)" frontend/src | while read -r f; do
  count=$(rg -c "^(export\s+)?(function|const)\s+[A-Z]\w*\s*[:=(][^{]*(ReactElement|JSX\.Element|ReactNode|FC\s*<)" "$f")
  [ "$count" -gt 1 ] && echo "$f: $count components"
done
```

**Detects**: files declaring ≥ 2 components.
**Fix**: Extract additional components to sibling files. Helpers ≥ 20 LOC get their own folder; < 20 LOC get a sibling `.tsx` + `.types.ts`.

### 8. Inline styles (Critical / Warning per case)

```bash
rg --type tsx -n "style=\{\{" frontend/src | rg -v "'--" | rg -v "\\\${"
```

**Detects**: inline `style={{...}}` that isn't CSS-variable injection (`style={{ '--foo': x }}`) and isn't a runtime-computed template literal (`style={{ width: \`${pct}%\` }}`). Remaining hits are static inline styles that must move to Tailwind utilities.
**Fix**: Replace with Tailwind classes. CSS-var values use arbitrary value syntax (`className="border-[var(--border)]"`).

### 9. Global CSS import in component files (Critical)

```bash
rg --type tsx -n "^import\s+['\"][^'\"]+\.css['\"]" frontend/src | rg -v "\.module\.css"
```

**Detects**: component `.tsx` files importing global CSS. Only `.module.css` scoped imports are allowed in components. The one exemption is `ui/index.ts` importing `./components.css` (aggregated BEM library CSS imported once).
**Fix**: Either convert to Tailwind utilities or move the import into a library-level `index.ts` aggregation.

### 10. Direct network calls outside exempt paths (Critical)

```bash
rg --type ts --type tsx -n "\\b(fetch\\(|axios\\.|new\\s+WebSocket\\()" frontend/src \
  | rg -v "core/api/" \
  | rg -v "core/websocket/wsClient\\.ts" \
  | rg -v "core/audio/audioEngine\\.ts"
```

**Detects**: direct `fetch()` / `axios` / `new WebSocket()` outside `@core/api/*` (RTK Query), `@core/websocket/wsClient.ts`, and the legitimate Web-Audio asset-loader in `core/audio/audioEngine.ts`.
**Fix**: Convert to RTK Query endpoint (REST) or route through `wsClient` (WS).

### 11. Cross-feature imports (Warning)

```bash
for f in $(rg --type ts --type tsx -l "@features/" frontend/src/features); do
  own=$(echo "$f" | sed -E 's#.*frontend/src/features/([^/]+)/.*#\1#')
  rg -n "@features/([^/'\"]+)" "$f" | rg -v "@features/$own" | grep -v '^$' \
    && echo "  ↑ in $f (own feature: $own)"
done
```

**Detects**: a file under `features/<X>/` importing from `@features/<Y>/` where X ≠ Y. Features must not depend on each other directly.
**Fix**: Lift the shared code to `@common/*` or `@core/*`, depending on whether it's types/utilities or infrastructure.

### 12. Banned TypeScript features (Critical)

```bash
rg --type ts --type tsx -n "(:\\s*any\\b|\\bas\\s+any\\b|//\\s*@ts-ignore|!\\.|!\\[)" frontend/src
```

**Detects**: `: any`, `as any`, `@ts-ignore`, non-null assertion chains (`foo!.bar`). All four are forbidden.
**Fix**: Write the correct type, narrow properly, or refactor until the cast is unnecessary.

### 13. Orb engine modification (Critical)

```bash
git diff --name-only main -- frontend/src/ui/orb/orbEngine.ts
```

**Detects**: any modification to the Three.js orb engine. The file is a project-level black box.
**Fix**: Revert `orbEngine.ts` changes; route the behavior through `setState` / `setAnalyser` / `destroy` at the call site instead.

---

## Report format

Produce the final report in this structure:

```markdown
## Critical (must fix before merge)

- `[frontend/src/features/foo/components/Foo.tsx:42]` — `type FooProps = {...}` → change to `interface`
- `[frontend/src/features/foo/components/Foo.tsx:88]` — second component `function FooHelper` in same file → extract to `FooHelper.tsx` sibling

## Warnings (should fix, not blocking)

- `[frontend/src/features/mail/hooks/useMail.ts:12]` — imports from `@features/agenda` (cross-feature) → lift the shared type to `@common/types`

## Suggestions (optional)

- Consider extracting `renderBadge` utility to `@common/utils/renderBadge.ts`

## Verdict

`PASS` (no Critical findings) or `NEEDS_CHANGES` (has Critical findings).
```

---

## When to run

- **After every batch** of feature work, before the commit.
- **Before merging a PR** against `main`.
- **After any byte-for-byte port** from legacy code — the port likely inherits violations from the source.
- **When onboarding a new agent** that hasn't internalized the rules — the report gives a concrete to-do list.

## Notes

- The multi-component check (#4) uses a heuristic; it may produce false positives for utility functions that return JSX inline (like `renderFoo = () => <span>…</span>`). Verify each hit manually.
- The inline-style filter (#5) uses a negative regex to exclude CSS-variable and template-literal patterns. If you see a legitimate hit in the output, add it to the whitelist.
- The cross-feature check (#8) is pure grep — it doesn't handle re-exports. If feature A imports from `@common` which re-exports from feature B, that will slip through. Manual spot-check is needed for subtle violations.
