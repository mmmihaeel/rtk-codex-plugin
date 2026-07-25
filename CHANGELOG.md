# Changelog

This changelog records user-visible RTK Codex Plugin releases.

## [Unreleased]

## [0.1.0] - 2026-07-25

### Included

- PreToolUse classification for supported shell command payloads;
- optional `rtk rewrite <command>` integration with bounded validation and
  fail-open behavior;
- pre-execution guarding for recognized long-line inspection shapes;
- PostToolUse byte, line, and best-effort aggregate-turn budgets;
- local artifact preservation for qualifying guarded or compacted output;
- stream, parallel-tool, wrapper, bypass, and Pitlane pass-through handling;
- standard-library test coverage for the public behavior surface.

### Documentation

- added architecture, decision-flow, sequence, and state-lifecycle diagrams;
- documented Python 3.11+ and POSIX requirements;
- documented native Windows exclusion and WSL2 operation;
- added pinned release installation, update, rollback, and uninstall guidance;
- documented every output-budget override and state path;
- documented artifact sensitivity, permissions, retention, and trust
  boundaries;
- added compatibility, troubleshooting, contribution, and security guides.

### Release scope

- POSIX plugin/source tarball;
- SHA-256 integrity manifest;
- no bundled RTK executable;
- no native Windows, PyPI, or npm package;
- no signed provenance or reproducible-build claim.

[Unreleased]: https://github.com/mmmihaeel/rtk-codex-plugin/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mmmihaeel/rtk-codex-plugin/releases/tag/v0.1.0
