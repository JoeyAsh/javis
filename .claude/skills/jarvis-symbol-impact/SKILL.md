---
name: jarvis-symbol-impact
description: Find every caller / referencing site for a Python or TypeScript symbol via Serena. Use for refactor planning ("if I change this signature, what breaks?") or before deleting a symbol. Returns a list of file:line references.
---

# JARVIS symbol-impact skill

## When to use

Use this skill before changing a public function signature, renaming an exported symbol, or deleting a public API. It is cheaper and more accurate than `rg`-based reference search because it understands TypeScript types and Python imports.

## Inputs

- `<name_path>` — Serena name path. Examples: `MailPanel`, `useMail/return`, `WsClient/subscribe`, `parse_wake_word`. Pattern: `<symbol>` or `<class>/<member>` or `<file_stem>/<symbol>`.
- `<relative_path>` (optional) — limit the search to a file or directory under the project root.

## Steps

1. Resolve the symbol:
   mcp__serena__find_symbol(name_path=<name_path>, relative_path=<relative_path>, include_body=false)

2. List all references:
   mcp__serena__find_referencing_symbols(name_path=<name_path>, relative_path=<relative_path>)

3. Group results by file. Report each as `<file>:<line> — <containing-symbol>`.

## Output format

```
## References to <name_path>

### frontend/src/features/mail/components/MailPanel/MailPanel.tsx
- :42 — MailPanel.handleClick

### frontend/src/app/store.ts
- :17 — rootReducer

Total: <N> references in <M> files.
```

## When NOT to use

- For pure ripgrep-style string search — use `Grep` instead. Serena understands semantics; for finding all usages of a string literal, that's overkill.
- For symbols defined inside test files only — Serena indexes those but the impact is usually irrelevant.
