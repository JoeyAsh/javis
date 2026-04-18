# JARVIS Ops

## systemd user service

Run JARVIS backend as a systemd user service with auto-restart on crash:

```bash
cp ops/jarvis-backend.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now jarvis-backend
```

Logs: `/tmp/jarvis-run.log` (or `journalctl --user -u jarvis-backend -f`).

Auto-restart triggers:
- Native crashes (heap corruption in onnxruntime / ctranslate2 etc.)
- Unhandled asyncio exceptions
- OOM kills
- Any exit with non-zero status

`RestartSec=3` means recovery in ≤5s even in worst case.
