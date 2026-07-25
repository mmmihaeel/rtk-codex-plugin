<h1 align="center">rtk-codex-plugin</h1>

<p align="center">
  <strong>Keep Codex shell output useful before it burns the context window.</strong>
</p>

<p align="center">
  A small Codex-compatible shell plugin for command rewrite, bounded long-line output, and artifact-backed output compaction.
</p>

<p align="center">
  <a href="https://github.com/mmmihaeel/rtk-codex-plugin/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/mmmihaeel/rtk-codex-plugin/ci.yml?branch=main&style=for-the-badge" alt="CI status">
  </a>
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="MIT License">
  </a>
  <img src="https://img.shields.io/badge/Python-3-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3">
  <img src="https://img.shields.io/badge/Codex-Plugin%20Hooks-111111?style=for-the-badge" alt="Codex plugin hooks">
</p>

<p align="center">
  <a href="./docs/install.md">Install</a>
  ·
  <a href="./docs/compatibility.md">Compatibility</a>
  ·
  <a href="./docs/stack.md">Stack Fit</a>
</p>

`rtk-codex-plugin` adds a shell-focused `PreToolUse` hook for Codex-compatible
runtimes. It has three jobs:

- route eligible Bash/`exec_command` calls through `rtk rewrite` for more
  compact output;
- wrap risky long-line inspections with a bounded output guard;
- compact medium/large model-visible tool output after execution while
  preserving the full raw output, including `write_stdin` streams, in local
  artifacts.

The guard is useful even when `rtk` is not installed. Rewrite mode is optional
and activates only when the `rtk` binary is available in `PATH`.

## Part of the Codez stack

The Codez stack is modular. Each layer can be used on its own unless a higher
layer explicitly opts into it.

| Layer | Public surface | Responsibility | Dependency |
| --- | --- | --- | --- |
| [Codez](https://github.com/mmmihaeel/codez) | Codex-compatible runtime | App Server v2, goal RPC, long-session hardening, prompt pruning, and plugin hooks | Does not require Teledex |
| [RTK Codex Plugin](https://github.com/mmmihaeel/rtk-codex-plugin) | Optional Codex plugin | Shell/token safety through `rtk rewrite` and bounded output guarding | Requires a Codex-compatible plugin-hook runtime; does not require Teledex |
| [Pitlane Codex Plugin](https://github.com/mmmihaeel/pitlane-codex-plugin) | Optional Codex plugin | Code-navigation/token-saving rewrites through a host-local `pitlane` CLI | Requires a Codex-compatible plugin-hook runtime and local `pitlane`; does not require Teledex |
| [Teledex](https://github.com/mmmihaeel/teledex) | Telegram gateway/session layer | Topics, queues, live steer, `/goal` UX, and delivery/recovery around durable agent sessions | Full mode is optimized for Codez App Server v2; upstream `codex exec --json` is legacy compatibility only |

## Why People Use It

- avoid huge JSONL, log, and prompt-capture lines flooding the model context
- keep simple shell exploration compact without changing test or machine
  command semantics
- preserve no-rewrite command semantics for `rg --files`, `git status --short`,
  `jq`/JSON modes, counts, lists, direct `rg`/`grep` searches, build/test
  commands, Docker commands, and interactive commands while still compacting
  oversized model-visible output
- install as a small plugin instead of changing every shell command by hand

## Mental Model

| Piece | Role |
| --- | --- |
| Codex-compatible runtime | executes `PreToolUse` hooks before shell calls |
| `rtk-codex-hook` | decides whether a command should be guarded, rewritten, or left alone |
| `rtk-output-guard` | caps per-line and total stdout for risky inspections |
| `rtk-output-post-hook` | compacts large model-visible shell output with artifact refs |
| optional `rtk` binary | rewrites eligible commands into a compact shell form |

Architecture at a glance:

```text
Codex shell tool call
  -> PreToolUse hook
     -> risky JSONL/log/prompt inspection? run through rtk-output-guard
     -> otherwise eligible simple command? ask rtk rewrite
     -> no-rewrite/build/test/Docker/interactive command? pass through unchanged
  -> PostToolUse hook
     -> medium/large model-visible output? summary + full local artifact
```

## Highlights

- bounds known long-line inspection shapes before execution
- bounds medium/large model-visible output after execution, including large
  pass-through command output unless explicitly bypassed
- works without `rtk` for output guarding
- skips rewrite when exact stdout matters
- uses plain Python scripts and a small plugin manifest
- designed to work standalone and to fit the modular Codez stack

## Quick Start

Clone the plugin into the plugin cache used by your Codex-compatible runtime.
One common cache layout looks like this:

```bash
codex_home="${CODEX_HOME:-$HOME/.codex}"
git clone https://github.com/mmmihaeel/rtk-codex-plugin \
  "$codex_home/plugins/cache/github/rtk-codex-plugin/local"
```

Enable plugin hooks and the plugin key that matches your install location:

```toml
[features]
plugins = true
plugin_hooks = true

[plugins."rtk-codex-plugin@github"]
enabled = true
```

Run the focused test suite:

```bash
make test
```

Read next:

- [Install](./docs/install.md)
- [Compatibility](./docs/compatibility.md)
- [Stack Fit](./docs/stack.md)

## Notes

- `rtk` rewrite is optional; install `rtk` separately when you want rewrite mode.
- output guarding stays active without `rtk`
- the plugin is intentionally shell-hook-only; gateway/session behavior belongs
  in higher-level tools
