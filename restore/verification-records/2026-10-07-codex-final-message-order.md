# Codex WhatsApp Final Message Ordering

- Date: 2026-10-07 UTC
- Bridge source: `/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/whatsapp_bridge.js`
- Baseline source revision: `81e845e89c6d3c97bcf5db003e3682d9c7c913fe`
- SHA-256 before this change: `21db8cca0ec559449929bb10fb26d48466229cb69ab2cd36da2dd9e06ffb1be7`
- SHA-256 after this change: `b5173b0e49b98f490cb5a1426f4acafb199aa39aa09a0bc76a5f1d969ff0b916`
- Pre-change backup: `/home/azureuser/.webterminal/bridge_backups/whatsapp_bridge.js.pre-codex-final-order-20261007T095048Z`
- Change: buffer a Codex final answer when it precedes its `task_complete` event, deliver the completion notice first, then deliver the existing formatted final response. Keep the response framing and session footer.
- Validation: `node --check webterminal/whatsapp_bridge.js` passed; `git diff --check -- webterminal/whatsapp_bridge.js` passed.
- Runtime state: bridge PID `649744` was running from the source path before restart. The `/home/azureuser/.webterminal` path resolves to the same source directory. An idle-gated restart was started with PID `650393`; its completion and live message ordering have not yet been verified.
- Limitation: no live Codex turn was sent to test WhatsApp ordering. The user-scoped systemd bus was unavailable, and the umbrella `agy-agents.service` was not restarted because it supervises multiple agents.
