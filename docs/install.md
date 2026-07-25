# Install

Install RTK Codex Plugin inside the same POSIX environment that runs the agent
runtime.

## Prerequisites

- Python 3.11 or later;
- Linux, WSL2, or another compatible POSIX environment;
- Git for the pinned-clone path, or `tar` for the release archive;
- a runtime implementing the required plugin and hook contracts;
- optional: a compatible `rtk` executable on `PATH` for command rewriting.

Native Windows is not supported in `v0.1.0`. On Windows, open WSL2 and perform
the clone, extraction, configuration, and runtime launch inside Linux.

## Option 1: pinned Git installation

```bash
python3 --version

codex_home="${CODEX_HOME:-$HOME/.codex}"
plugin_dir="$codex_home/plugins/cache/github/rtk-codex-plugin/local"

git clone --branch v0.1.0 --depth 1 \
  https://github.com/mmmihaeel/rtk-codex-plugin.git \
  "$plugin_dir"

test -x "$plugin_dir/hooks/rtk-codex-hook"
test -x "$plugin_dir/hooks/rtk-output-guard"
test -x "$plugin_dir/hooks/rtk-output-post-hook"
```

Cloning a release tag avoids silently moving with `main`.

## Option 2: release archive

Download `rtk-codex-plugin-v0.1.0.tar.gz` and `SHA256SUMS` from the
[v0.1.0 release](https://github.com/mmmihaeel/rtk-codex-plugin/releases/tag/v0.1.0).

```bash
sha256sum -c SHA256SUMS

codex_home="${CODEX_HOME:-$HOME/.codex}"
plugin_dir="$codex_home/plugins/cache/github/rtk-codex-plugin/local"

mkdir -p "$plugin_dir"
tar -xzf rtk-codex-plugin-v0.1.0.tar.gz \
  --strip-components=1 \
  -C "$plugin_dir"

test -x "$plugin_dir/hooks/rtk-codex-hook"
```

The release uses a POSIX tar archive so LF endings and executable modes are
preserved. If the executable checks fail:

```bash
chmod 0755 \
  "$plugin_dir/hooks/rtk-codex-hook" \
  "$plugin_dir/hooks/rtk-output-guard" \
  "$plugin_dir/hooks/rtk-output-post-hook"
```

## Activate the plugin

Add the matching plugin key to the runtime configuration:

```toml
[features]
plugins = true
plugin_hooks = true

[plugins."rtk-codex-plugin@github"]
enabled = true
```

The exact key depends on the runtime and installation source. Restart or reload
the runtime after changing plugin configuration.

If the runtime exposes App Server hook inspection, call `hooks/list` for the
current working directory and confirm both stages are discovered:

- PreToolUse: `rtk-codex-hook`;
- PostToolUse: `rtk-output-post-hook`.

## Verify the checkout

From the plugin directory:

```bash
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool hooks/hooks.json >/dev/null
python3 tests/test_rtk_codex_hook.py
```

Expected public-suite result:

```text
Ran 50 tests
OK (skipped=1)
```

The intentional skip covers a private projection exporter that is not included
in the public repository.

## Guard-only operation

No separate RTK install is required for the recognized pre-execution output
guard or PostToolUse compaction. Without `rtk` on `PATH`, eligible rewrite
requests simply keep their original command.

For rewrite mode, verify only the interface this plugin consumes:

```bash
command -v rtk
rtk rewrite 'example command'
```

The plugin does not install, pin, or attest the external executable.

## Update

For a tag-based clone:

```bash
cd "$plugin_dir"
git fetch --tags origin
git checkout v0.1.0
```

Replace `v0.1.0` with a reviewed newer release tag. Read the changelog and rerun
the test suite before enabling the new version.

## Roll back or uninstall

Disable the plugin in runtime configuration first:

```toml
[plugins."rtk-codex-plugin@github"]
enabled = false
```

Restart the runtime, then move the checkout to a reversible backup:

```bash
mv "$plugin_dir" "${plugin_dir}.disabled-v0.1.0"
```

Artifact and budget state is stored separately and is intentionally not removed
by uninstalling the plugin. Review
[Configuration](./configuration.md#state-locations) and
[Security](../SECURITY.md) before cleaning that data.

## Development checkout

Contributors can track `main` in a separate development path:

```bash
git clone https://github.com/mmmihaeel/rtk-codex-plugin.git
cd rtk-codex-plugin
python3 tests/test_rtk_codex_hook.py
```

Do not point production plugin configuration at a moving development checkout
without an intentional update policy.

See [Troubleshooting](./troubleshooting.md) for hook discovery, line endings,
and platform diagnostics.
