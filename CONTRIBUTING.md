# Contributing

RTK Codex Plugin is intentionally small, but classifier and output-budget
changes can alter shell behavior. Contributions should be narrow, explicit
about command semantics, and backed by focused tests.

## Environment

Use Python 3.11+ on Linux, WSL2, or another POSIX environment:

```bash
python3 --version
git clone https://github.com/mmmihaeel/rtk-codex-plugin.git
cd rtk-codex-plugin
```

The project uses only the Python standard library.

## Run verification

```bash
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool hooks/hooks.json >/dev/null
test -x hooks/rtk-codex-hook
test -x hooks/rtk-output-guard
test -x hooks/rtk-output-post-hook
make test
```

The public suite discovers 50 tests: 49 pass and one public-projection exporter
check is intentionally skipped because that exporter is not included here.

## Change expectations

For classifier changes, add cases covering:

- the intended rewrite or guard path;
- neighboring pass-through and exact-output shapes;
- wrappers, environment prefixes, quoting, and shell-control boundaries;
- missing, invalid, or failing external RTK behavior;
- Pitlane-owned shapes when integration ordering could change.

For PostToolUse changes, cover:

- byte and line thresholds;
- summary-smaller checks and artifact removal;
- aggregate turn state;
- `write_stdin` and parallel payloads;
- bypass markers;
- sensitive path and filename handling.

Do not add benchmark, token-saving, security, or cross-runtime claims without
reproducible evidence.

## Documentation

Update public documentation when a change affects:

- supported Python or platforms;
- plugin/hook payload contracts;
- environment variables or default limits;
- artifact locations, permissions, or retention;
- bypass behavior;
- optional RTK interface;
- ecosystem ordering or compatibility.

All public prose must remain English. Verify Markdown formatting, local links,
and examples before opening a pull request.

## Pull requests

Describe:

- the user-visible behavior;
- why the selected classifier boundary is safe enough for its intended role;
- exact tests run;
- platform/runtime combinations not tested;
- security, artifact, or release impact.

Contributions are accepted under the [MIT License](./LICENSE).
