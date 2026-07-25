---
name: rtk
description: "Use when debugging or explaining the RTK Codex plugin: PreToolUse shell-command rewrites, PostToolUse output compaction/artifacts, rtk-output-guard truncation, pass-through/exact-output behavior, and emergency bypass env vars."
---

# RTK Codex Hook

RTK is integrated into Codex through this plugin's `PreToolUse` hook, not
through host-wide PATH wrappers.

## Behavior

- The hook receives Codex `PreToolUse` JSON for `Bash` and compatible
  `exec_command` tool calls, accepting either `tool_input.command` or
  `tool_input.cmd`.
- It calls `rtk rewrite <command>` only for eligible simple shell commands.
- If RTK returns a replacement, the hook returns `updatedInput.command`.
- If RTK has no rewrite or the command must not be rewritten, the hook emits
  nothing and Codex runs the original command.
- Risky line-limited log/data inspections such as `rg ... *.jsonl | head`,
  `grep ... *.log | tail`, and direct `head`/`tail`/`sed -n` on JSONL/log files
  are wrapped by `rtk-output-guard`, which caps per-line and total output.
- The `PostToolUse` hook compacts medium/large model-visible shell output into
  a short summary while preserving full raw text under the local RTK artifact
  directory. No-rewrite/pass-through does not mean unlimited raw output.

## Pass-Through

The hook deliberately does not rewrite:

- `rg --files`
- native `find`, direct `rg`/`grep` searches, `grep` count/list/quiet modes,
  and `rg` file-list/JSON/count/list/stats/vimgrep modes
- commands with pipes, redirects, command substitution, shell separators, or
  other multi-command shell control, except line-limited inspection pipelines
  that are safely bounded by `rtk-output-guard`
- JSON, porcelain, and machine-readable output modes
- build commands and Docker commands
- test commands such as `cargo test`, `go test`, `pytest`, `jest`, `vitest`,
  `rspec`, and package-manager test/check scripts

## Emergency Bypass

Set any of these environment variables to a non-empty value to disable the hook:

- `RTK_CODEX_HOOK_DISABLE=1`
- `RTK_CODEX_BYPASS=1`
- `RTK_DISABLE=1`
- `RTK_DISABLED=1`
