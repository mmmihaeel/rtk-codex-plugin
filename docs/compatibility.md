# Compatibility

RTK Codex Plugin is designed for Codez and runtimes that implement the same
plugin and hook contracts. A Codex-derived name alone is not a compatibility
guarantee.

## Platform matrix

| Environment          | `v0.1.0` status           | Notes                                                                                     |
| -------------------- | ------------------------- | ----------------------------------------------------------------------------------------- |
| Ubuntu / Linux POSIX | Verified                  | GitHub Actions and the complete test suite                                                |
| Ubuntu on WSL2       | Verified                  | Complete test suite run locally                                                           |
| macOS                | Expected, not CI-verified | Required POSIX APIs are available, but this release has no macOS CI evidence              |
| Native Windows       | Unsupported               | `fcntl`, POSIX shell syntax, executable shebangs, and file-mode expectations are required |
| Containers           | Environment-dependent     | Works when Python 3.11+, POSIX tools, writable state, and runtime hooks are present       |

Python 3.11+ is required because the hooks use `datetime.UTC`; the PostToolUse
budget lock also depends on `fcntl`.

## Runtime contract

Full functionality requires:

- `.codex-plugin/plugin.json` discovery;
- `hooks/hooks.json` loading;
- `${PLUGIN_ROOT}` expansion;
- executable command hooks;
- PreToolUse `updatedInput` replacement;
- PostToolUse response feedback from stderr with exit code `2`;
- string `tool_response` payloads for output compaction.

Manifest matchers cover:

| Stage       | Tool identifiers                                                                              |
| ----------- | --------------------------------------------------------------------------------------------- |
| PreToolUse  | `Bash`, `exec_command`, `functions.exec_command`                                              |
| PostToolUse | PreToolUse identifiers plus `write_stdin`, `functions.write_stdin`, `multi_tool_use.parallel` |

The scripts can recognize selected namespaced `exec_command` forms internally,
but the runtime invokes only identifiers matched by the manifest.

## Codez relationship

[Codez](https://github.com/mmmihaeel/codez) is the primary documented runtime
because it exposes compatible plugin discovery, PreToolUse input replacement,
PostToolUse handling, and `hooks/list`.

The RTK repository verifies the hook scripts in isolation. It does not currently
contain a cross-repository live installation test against a tagged Codez
release, so compatibility is an interface-level claim rather than an
end-to-end certification.

## Optional RTK interface

Rewrite mode expects:

```text
rtk rewrite <command>
```

Contract:

- executable name: `rtk` on `PATH`;
- accepted exit codes: `0` and `3`;
- output: UTF-8 replacement command on stdout;
- timeout: four seconds;
- maximum accepted replacement: 16 KiB;
- control characters and shell-control markers: rejected.

No provider, distribution, or minimum RTK version is bundled or attested by
this repository. Missing or rejected RTK output preserves the original command.

## PreToolUse policy

The classifier broadly preserves the original command for:

- shell-control or multi-command forms, except recognized bounded inspection
  pipelines;
- tests and builds;
- direct Git, JQ, `rg`, `grep`, and `find`;
- JSON, porcelain, count, list, and other machine-readable modes;
- Docker, interactive, live-control, and binary-output commands;
- recognized Pitlane navigation shapes.

Recognized line-limited inspection pipelines, direct risky-file limiters, and
`codex debug prompt-input` can be wrapped by the bounded guard before those
general pass-through rules.

Pass-through applies only to the command. Large output from these families can
still be compacted after execution.

## PostToolUse contract

The hook operates only on a non-empty string `tool_response`. It can preserve
the complete text received from the runtime in a local artifact, but cannot
recover content truncated before PostToolUse.

Successful compaction requires:

- a configured threshold to be exceeded;
- a summary materially smaller than the received response;
- a runtime that interprets exit code `2` and stderr as compact model feedback.

Aggregate accounting is best-effort rather than a strict concurrency-safe
quota.

## External integrations

- No Teledex or gateway is required.
- Pitlane is optional and independently released.
- Loading RTK before Pitlane is the recommended order for their documented
  classifier responsibilities, but no cross-plugin end-to-end test is claimed.

See [Stack fit](./stack.md).

## Release scope

`v0.1.0` publishes a POSIX source/plugin archive. It does not publish:

- a native Windows package;
- a PyPI or npm package;
- an RTK executable;
- a Codez runtime;
- a signed or reproducible-build attestation.
