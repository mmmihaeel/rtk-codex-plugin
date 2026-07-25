# Security Policy

RTK Codex Plugin is trusted local hook code. It can inspect and replace shell
tool input, observe tool output supplied by the runtime, call a local
executable, and persist raw text to disk. It is a context-budget guardrail, not
a sandbox, approval system, command sanitizer, secret scanner, or
data-loss-prevention boundary.

## Supported versions

Security fixes target the latest tagged release and the current default branch.

| Version        | Supported                                |
| -------------- | ---------------------------------------- |
| Latest release | Yes                                      |
| Default branch | Yes                                      |
| Older releases | No separate long-term support commitment |

## Reporting a vulnerability

Use a
[private GitHub security advisory](https://github.com/mmmihaeel/rtk-codex-plugin/security/advisories/new)
for sensitive issues. Include:

- affected release or commit;
- runtime and Python versions;
- operating environment;
- minimal reproduction;
- whether the issue affects PreToolUse, guarded execution, PostToolUse, or
  artifact state;
- expected and observed impact.

Do not attach real credentials, private source, raw production artifacts, or
active exploit data to a public issue.

## Trusted-code model

Enabling the plugin expands the runtime's trusted computing base:

- the hook scripts execute with the runtime user's permissions;
- the optional `rtk` executable is resolved from `PATH` and trusted;
- an accepted RTK replacement can change command semantics;
- a guard wrapper can change process shape and merge stderr into stdout;
- local plugin updates change executable behavior.

Pin reviewed release tags, protect the installation directory, and control
`PATH`. Runtime approvals and sandbox policy must remain enabled independently.

## Command boundaries

The pre-hook rejects obviously unsuitable RTK output such as control characters,
shell-control markers, and oversized replacements. Those are syntactic checks,
not a proof of safety or semantic equivalence.

When the pre-execution guard is selected, the wrapped command runs through the
POSIX shell. Depending on the host runtime, approval or logging surfaces may see
the Python/Base64 wrapper rather than the original command. Operators should
not treat the wrapper as authorization.

## Sensitive artifacts

Artifacts may contain:

- credentials or tokens printed by commands;
- private source code;
- logs and personal data;
- prompts, tool responses, or infrastructure details.

The plugin requests `0700` directories and `0600` files on POSIX, but
permissions are best-effort and filesystem-dependent. Artifacts:

- are not encrypted;
- have no automatic expiry;
- have no size quota;
- persist after plugin uninstall;
- must not be uploaded without review.

Use `RTK_CODEX_ARTIFACT_DIR` and `RTK_CODEX_BUDGET_DIR` to place state on an
appropriate protected filesystem. Review the resolved paths before manual
cleanup.

SHA-256 in a compact summary identifies the stored bytes. It does not prove
authenticity, encrypt the content, or prevent later modification.

## Host truncation

PostToolUse preserves the complete string supplied in `tool_response` when
compaction succeeds. If the runtime, shell adapter, transport, or another hook
truncated content earlier, the plugin cannot recover it.

## Bypass

`RTK_CODEX_BYPASS=1` intentionally disables both rewrite/guard selection and
PostToolUse compaction for recognized command/stream forms. Use it narrowly:
raw output may be large or sensitive and becomes model-visible under the host
runtime's normal handling.

## Platform boundary

The complete `v0.1.0` plugin requires Python 3.11+ on POSIX. Native Windows is
unsupported. Run under WSL2 instead of attempting to weaken or replace POSIX
locking and executable-script assumptions without a reviewed code change.

## Release verification

Download releases only from the
[GitHub releases page](https://github.com/mmmihaeel/rtk-codex-plugin/releases)
and verify `SHA256SUMS`. Checksums provide transport integrity, not a signature
or reproducible-build attestation.
