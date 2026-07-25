# Install

This plugin expects a Codex-compatible runtime that supports plugin manifests
and `PreToolUse` hooks.

Clone the plugin into the plugin cache used by your runtime. One common cache
layout is:

```bash
codex_home="${CODEX_HOME:-$HOME/.codex}"
git clone https://github.com/mmmihaeel/rtk-codex-plugin \
  "$codex_home/plugins/cache/github/rtk-codex-plugin/local"
```

Enable plugin support in your Codex config:

```toml
[features]
plugins = true
plugin_hooks = true

[plugins."rtk-codex-plugin@github"]
enabled = true
```

If your runtime assigns a different marketplace or local plugin key, enable the
key that matches its cache layout.

`rtk` is optional. If it is missing, rewrite mode is skipped and bounded-output
guarding still works for recognized risky command shapes.

No Teledex or gateway install is required for local plugin usage.
