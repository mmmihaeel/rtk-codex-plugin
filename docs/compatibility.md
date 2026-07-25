# Compatibility

The plugin is intended for Codex-compatible runtimes that support:

- plugin manifests via `.codex-plugin/plugin.json`;
- hook declarations via `hooks/hooks.json`;
- `PreToolUse` and `PostToolUse` hooks for shell/Bash or compatible
  `exec_command` tool calls;
- `${PLUGIN_ROOT}` expansion in hook commands.

Known integration layers:

- [Codez](https://github.com/mmmihaeel/codez) is the recommended public runtime
  layer when you want plugin hooks plus token-aware context behavior.
- Other Codez/Codex-compatible runtimes can execute the hook directly if they
  support plugin-loaded `PreToolUse` shell hooks.
- Telegram or remote-worker gateways can sync the plugin to worker machines,
  but no gateway is required for local usage. [Teledex](https://github.com/mmmihaeel/teledex)
  is the Codez-first Telegram gateway layer; its full mode is optimized for
  Codez App Server v2, while upstream `codex exec --json` is legacy
  compatibility only.

`rtk` command rewrite requires the `rtk` binary in `PATH`. Output guarding does
not require `rtk`.

## Pass-Through Policy

The hook avoids rewriting commands where exact output is expected:

- tests and package-manager check commands
- build commands
- direct `rg`/`grep` searches, including regex-like patterns
- Docker commands
- machine-readable modes such as JSON, porcelain, counts, and file lists
- interactive commands
- binary-ish output commands
- shell-control forms that are not recognized risky inspection pipelines

Recognized JSONL, log, and prompt-input inspection shapes are guarded before
execution so a single long line cannot dominate the context window. Larger
model-visible output is compacted after execution with a local artifact path
and hash, including pass-through command families such as standalone
`jq`/JSON-style commands, Docker/SSH output, build/test output, Git path
streams, `write_stdin` stream output, and parallel-wrapper output when the
runtime exposes them through `PostToolUse`. Set `RTK_CODEX_BYPASS=1` when raw
model-visible output must be preserved above the caps.

## Dependency Boundary

RTK does not require Teledex. It only requires a Codex-compatible runtime that
supports plugin-loaded `PreToolUse` shell hooks. Teledex can install or sync
RTK for workers, but gateway/session behavior stays outside this plugin.
