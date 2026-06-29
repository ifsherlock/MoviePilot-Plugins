# Codex Windows Repair Plan

## Goal

Repair local Codex Desktop support for Computer Use, browser/chrome plugins, and MCP/plugin marketplace loading.

## Checklist

- [x] Read `codex-windows-fast-patch` instructions and run skill self-update.
- [x] Create a portable Codex state backup before config/plugin changes.
- [x] Run read-only triage for package status, plugin marketplace loading, and Computer Use strict verification.
- [x] Repair local Computer Use / bundled marketplace / browser and chrome cache state.
- [x] Re-run strict verification and `codex plugin list`.
- [x] Escalate to MSIX repatch only if Desktop gates remain closed.
- [x] Summarize changed config files, including whether any `config.yaml` changed.

## Current Evidence

- Installed Desktop package: `OpenAI.Codex_26.623.8305.0_x64__2p2nqsd0c76g0`, `SignatureKind = Store`.
- `codex plugin list` fails because `openai-curated-local` does not contain a supported marketplace manifest.
- Computer Use strict verification fails because `computer-use\latest\.codex-plugin\plugin.json` is missing.
- State backup created at `C:\Users\jaysh\.codex\backups\portable-state\20260629-202002`.

## Final Status

- Restored `openai-curated-local` from `C:\Users\jaysh\.codex\.tmp\plugins` to `C:\Users\jaysh\.codex\marketplaces\openai-curated-local`.
- Rebuilt local `openai-bundled` marketplace/cache for `computer-use`, `browser`, and `chrome`.
- Installed patched Codex Desktop package; package now reports `SignatureKind = Developer`.
- Trusted MSIX signing certificate thumbprint `9428008A9D341A0A00EA28BD451A0CF1BDEA4B4E` in LocalMachine and CurrentUser stores.
- Verification passed: Computer Use client import ok, helper transport ok, plugin list loads, MCP list loads, sandbox smoke test outputs `OK`.
- No `config.yaml` or `config.yml` file was found under `C:\Users\jaysh\.codex`; only `config.toml` files were present.

## Phone Remote Control Repair

- [x] Read phone remote-control debug reference.
- [x] Create a fresh Codex portable-state backup.
- [x] Inspect current package, remote auth files, ASAR markers, and native markers.
- [ ] Verify or refresh isolated remote-control auth without changing main provider config.
- [ ] Patch remote-control MSIX when current package lacks required markers.
- [ ] Re-run Computer Use/browser/plugin/MCP/sandbox regression checks.
- [ ] Confirm phone pairing endpoint can load or identify the remaining external blocker.

### Current Diagnosis

- Desktop logs show `error sending request for url` for both `remote/control/server/pair` and remote plugin catalog requests to `chatgpt.com`.
- PowerShell direct requests to `https://chatgpt.com/` fail at SSL connection setup.
- Common local proxy ports `10808` and `7890` are not listening.
- `127.0.0.1:15727` is the CC Switch API proxy, but it does not support generic HTTPS `CONNECT` for `chatgpt.com` and returns 404 as a proxy.
- Current package does not contain phone remote-control patch markers; the existing remote-control ASAR patcher also needs 26.623 bundle-shape adaptation before it can be installed cleanly.
