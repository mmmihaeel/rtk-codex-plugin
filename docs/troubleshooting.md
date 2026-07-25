# Troubleshooting

Start with the runtime's plugin and hook inventory, then test the hook scripts
inside the same POSIX environment as the runtime.

## The plugin is not discovered

Check the expected layout:

```text
<plugin-root>/
├── .codex-plugin/plugin.json
├── hooks/hooks.json
├── hooks/rtk-codex-hook
├── hooks/rtk-output-guard
└── hooks/rtk-output-post-hook
```

Validate the manifests:

```bash
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool hooks/hooks.json >/dev/null
```

Confirm both runtime features and the correct installation-specific plugin key
are enabled. If available, use App Server `hooks/list` for the target working
directory and inspect load warnings.

## A hook is not executable

```bash
test -x hooks/rtk-codex-hook
test -x hooks/rtk-output-guard
test -x hooks/rtk-output-post-hook
```

Restore POSIX modes:

```bash
chmod 0755 hooks/rtk-codex-hook hooks/rtk-output-guard hooks/rtk-output-post-hook
```

If the checkout was created by native Windows Git, inspect line endings. CRLF
in a shebang script can produce a `bad interpreter` error. Clone or extract the
release inside WSL2, or convert the hook files back to LF.

## Native Windows fails

Native Windows is unsupported in `v0.1.0`. The complete hook pipeline requires
POSIX executable scripts, shell syntax, and `fcntl`.

Use WSL2 and run all of the following inside Linux:

- plugin installation;
- runtime launch;
- Python tests;
- artifact inspection.

## A command is not rewritten

This can be expected. PreToolUse preserves:

- explicit bypass;
- shell-control and multi-command forms;
- tests, builds, direct search, Git, JQ, Docker, interactive, live-control, and
  machine-readable commands;
- Pitlane-owned navigation shapes;
- commands when `rtk` is missing or returns an invalid replacement.

Check the optional executable:

```bash
command -v rtk
rtk rewrite 'the original command'
```

The plugin accepts only exit code `0` or `3`, waits four seconds, and rejects
empty, unchanged, oversized, control-containing, or shell-control output.

## A pass-through command still has compacted output

Pass-through preserves the **pre-execution command**. PostToolUse is a separate
stage and can compact large test, build, Git, JSON, Docker, SSH, stream, or
parallel output.

For one command that genuinely needs raw model-visible output:

```bash
RTK_CODEX_BYPASS=1 command
```

Unset the variable afterward.

## Output is compacted unexpectedly

Review the active values:

```bash
env | grep '^RTK_CODEX_'
```

Defaults:

- human-facing output: 5 KiB;
- general output: 12 KiB;
- aggregate turn output: 32 KiB;
- visible lines: 300.

See [Configuration](./configuration.md#posttooluse-budgets) for clamps and
overrides.

## No artifact was retained

An artifact is intentionally removed when the generated summary is not
materially smaller than the response. For compacted output, the summary includes
the artifact path and SHA-256.

The plugin stores only the response delivered to PostToolUse. If the host
runtime truncated content earlier, the artifact cannot restore it.

## Find local state

Unless overridden:

```bash
state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
find "$state_home/rtk-codex-plugin" -maxdepth 4 -type f -print
```

Artifacts can contain sensitive raw output and have no automatic retention.
Inspect paths and contents before any cleanup or upload.

## PostToolUse exits with code 2

For this plugin, exit code `2` with a summary on stderr is the successful
compaction feedback contract. A compatible runtime should recognize that
feedback and expose the compact summary appropriately to the model.

If the runtime treats it as a generic hook failure, that runtime does not
implement the required PostToolUse contract.

## Tests fail on Windows

Run the suite under Linux/WSL2:

```bash
python3 tests/test_rtk_codex_hook.py
```

Direct native-Windows subprocess execution cannot launch the extensionless
POSIX hook files and does not provide `fcntl`.

## CI passes but local execution fails

Compare:

- Python version (`3.11+`);
- POSIX environment;
- executable bits;
- LF line endings;
- plugin path and `${PLUGIN_ROOT}` expansion;
- filesystem permissions for artifact and budget roots;
- hook timeout behavior in the host runtime.

For sensitive or potentially exploitable failures, follow
[Security](../SECURITY.md) instead of posting raw artifacts publicly.
