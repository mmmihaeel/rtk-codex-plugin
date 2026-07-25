# Configuration

RTK Codex Plugin has two configuration layers:

1. runtime feature/plugin activation in the Codex configuration;
2. process environment variables controlling bypass, output budgets, and state
   locations.

## Runtime activation

```toml
[features]
plugins = true
plugin_hooks = true

[plugins."rtk-codex-plugin@github"]
enabled = true
```

The plugin key is installation-source-specific. Confirm the effective key and
hook definitions through the runtime's plugin or `hooks/list` inspection
surface.

## Canonical bypass

Use `RTK_CODEX_BYPASS=1` when exact model-visible output is required:

```bash
RTK_CODEX_BYPASS=1 command-that-must-remain-raw
```

The assignment must be part of the command environment in a position recognized
by the classifier, or set in the hook process environment. Unset the variable
to resume normal behavior; do not rely on `=0` because pre- and post-hook
parsing intentionally differs.

Accepted process-level disable aliases:

| Variable                 | Intended use                         |
| ------------------------ | ------------------------------------ |
| `RTK_CODEX_BYPASS`       | Canonical per-command/session bypass |
| `RTK_CODEX_HOOK_DISABLE` | Disable this plugin's hook behavior  |
| `RTK_DISABLE`            | Compatibility disable alias          |
| `RTK_DISABLED`           | Compatibility disable alias          |

Pass-through is not a bypass. It preserves the original command before
execution, while PostToolUse may still compact oversized output.

## PostToolUse budgets

All byte values count UTF-8 bytes.

| Variable                                   | Default |  Accepted range | Meaning                                                                                                        |
| ------------------------------------------ | ------: | --------------: | -------------------------------------------------------------------------------------------------------------- |
| `RTK_CODEX_HUMAN_OUTPUT_BYTES`             |   5,120 | 1,024–1,048,576 | Threshold for known human-facing, stream, parallel, build/test, shell-control/pipeline, and live-output shapes |
| `RTK_CODEX_VISIBLE_OUTPUT_BYTES`           |  12,288 | 1,024–1,048,576 | General single-response threshold                                                                              |
| `RTK_CODEX_VISIBLE_OUTPUT_LINES`           |     300 |       20–10,000 | General line-count threshold                                                                                   |
| `RTK_CODEX_AGGREGATE_VISIBLE_OUTPUT_BYTES` |  32,768 |     0–4,194,304 | Best-effort per-turn visible budget; `0` disables aggregate accounting                                         |
| `RTK_CODEX_SUMMARY_HEAD_BYTES`             |   4,096 |      512–32,768 | Preferred head excerpt size                                                                                    |
| `RTK_CODEX_SUMMARY_TAIL_BYTES`             |   2,048 |      256–32,768 | Preferred tail excerpt size                                                                                    |

Values outside the accepted range are clamped. Invalid integers fall back to
their defaults.

Example:

```bash
export RTK_CODEX_HUMAN_OUTPUT_BYTES=8192
export RTK_CODEX_VISIBLE_OUTPUT_BYTES=24576
export RTK_CODEX_AGGREGATE_VISIBLE_OUTPUT_BYTES=65536
```

The summary builder may reduce the configured head/tail excerpt further when
needed to ensure the compact feedback is materially smaller than the received
response.

## Fixed PreToolUse guard limits

The current plugin release does not expose environment overrides for the guard
selected by `rtk-codex-hook`.

| Control                     |  Value |
| --------------------------- | -----: |
| Visible bytes per line body |  4,096 |
| Visible output body         | 65,536 |

The guard emits status and artifact-reference text beyond the visible body
budget.

## Optional RTK contract

Command rewrite activates only when an executable named `rtk` is found on
`PATH`. The required interface is:

```text
rtk rewrite <command>
```

The plugin:

- waits at most four seconds;
- accepts exit code `0` or `3`;
- reads a UTF-8 replacement from stdout;
- rejects empty, unchanged, control-containing, shell-control, or over-16-KiB
  replacements;
- leaves the original command unchanged on missing, timed-out, invalid, or
  rejected output.

The plugin does not pin or install an RTK distribution. The operator owns that
executable's provenance and version.

## State locations

### Artifacts

Resolution order:

1. `RTK_CODEX_ARTIFACT_DIR`;
2. `$XDG_STATE_HOME/rtk-codex-plugin/artifacts`;
3. `~/.local/state/rtk-codex-plugin/artifacts`.

Pre-execution guard artifacts use an additional `pretool/` directory unless an
explicit override is set. PostToolUse artifacts use:

```text
<artifact-root>/<session>/<turn>/<timestamp>-<tool-use>-<sha-prefix>.txt
```

### Budget and bypass state

Resolution order:

1. `RTK_CODEX_BUDGET_DIR`;
2. `$XDG_STATE_HOME/rtk-codex-plugin/budgets`;
3. `~/.local/state/rtk-codex-plugin/budgets`.

This directory can contain:

- `<session>-<turn>.json` counters;
- matching `.lock` files;
- `stream-bypass/` marker files.

Example isolated configuration:

```bash
export RTK_CODEX_ARTIFACT_DIR="$PWD/.rtk-state/artifacts"
export RTK_CODEX_BUDGET_DIR="$PWD/.rtk-state/budgets"
```

Do not place those directories in a tracked repository.

## Permissions and retention

The plugin requests `0700` for state directories and `0600` for files on POSIX,
but enforcement is best-effort and depends on the filesystem. Files are not
encrypted.

There is no automatic retention, quota, or cleanup. Artifacts can contain
credentials, private source, logs, prompts, or other sensitive data. Inspect
the exact configured root before deleting anything, and never upload the state
directory blindly.

See [Security](../SECURITY.md) and
[Troubleshooting](./troubleshooting.md).
