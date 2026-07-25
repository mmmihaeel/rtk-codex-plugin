# Stack Fit

`rtk-codex-plugin` is useful as a standalone Codex-compatible plugin, but it is
also designed to sit in a larger local-agent stack.

## Part of the Codez stack

The Codez stack is modular. Each layer can be used on its own unless a higher
layer explicitly opts into it.

| Layer | Public surface | Responsibility | Dependency |
| --- | --- | --- | --- |
| [Codez](https://github.com/mmmihaeel/codez) | Codex-compatible runtime | App Server v2, goal RPC, long-session hardening, prompt pruning, and plugin hooks | Does not require Teledex |
| [RTK Codex Plugin](https://github.com/mmmihaeel/rtk-codex-plugin) | Optional Codex plugin | Shell/token safety through `rtk rewrite` and bounded output guarding | Requires a Codex-compatible plugin-hook runtime; does not require Teledex |
| [Pitlane Codex Plugin](https://github.com/mmmihaeel/pitlane-codex-plugin) | Optional Codex plugin | Code-navigation/token-saving rewrites through a host-local `pitlane` CLI | Requires a Codex-compatible plugin-hook runtime and local `pitlane`; does not require Teledex |
| [Teledex](https://github.com/mmmihaeel/teledex) | Telegram gateway/session layer | Topics, queues, live steer, `/goal` UX, and delivery/recovery around durable agent sessions | Full mode is optimized for Codez App Server v2; upstream `codex exec --json` is legacy compatibility only |

The plugin does not own sessions, chat delivery, host registries, or project
metadata. It only handles shell command rewrite and bounded output at the hook
layer.

## Plain Version

Codez runs the agent. RTK makes risky shell output safer and smaller. Pitlane
makes routine code browsing smaller by replacing safe source reads with indexed
CLI calls. Teledex is the Telegram/session gateway that can drive a runtime,
but it is not part of the Codez runtime itself.

RTK does not require Codez, Pitlane, or Teledex. Codez is linked because it has
a clean public repository and is the recommended runtime when you want plugin
hooks plus token-aware context behavior. Teledex is linked as the Codez-first
Telegram gateway layer; it can install or sync RTK for workers, but RTK remains
usable without any gateway.

## Plugin Order

When RTK and Pitlane are both enabled, load RTK before Pitlane. RTK handles
general shell-output safety; Pitlane then wins only for the narrow
code-navigation commands it accepts.
