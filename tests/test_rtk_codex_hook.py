#!/usr/bin/env python3

from __future__ import annotations

import base64
import json
import os
import shlex
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOOK = PLUGIN_ROOT / "hooks" / "rtk-codex-hook"
OUTPUT_GUARD = PLUGIN_ROOT / "hooks" / "rtk-output-guard"
OUTPUT_POST_HOOK = PLUGIN_ROOT / "hooks" / "rtk-output-post-hook"
BYPASS_ENV = [
    "RTK_CODEX_HOOK_DISABLE",
    "RTK_CODEX_BYPASS",
    "RTK_DISABLE",
    "RTK_DISABLED",
]

LEGACY_WRAPPER_BYPASS_ENV = [
    "RTK_DISABLE_WRAPPERS",
    "RTK_WRAPPERS_DISABLE",
]


def payload(
    command: str,
    *,
    tool_name: str = "Bash",
    input_key: str = "command",
    cwd: Path | None = None,
    workdir: Path | None = None,
) -> str:
    data = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": {input_key: command},
    }
    if cwd is not None:
        data["cwd"] = str(cwd)
    if workdir is not None:
        data["tool_input"]["workdir"] = str(workdir)
    return json.dumps(data)


def post_payload(
    command: str,
    response: str,
    *,
    turn_id: str = "turn-1",
    tool_name: str = "Bash",
    input_key: str = "command",
) -> str:
    return json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": tool_name,
            "session_id": "session-1",
            "turn_id": turn_id,
            "tool_use_id": "tool-1",
            "tool_input": {input_key: command},
            "tool_response": response,
        }
    )


class RtkCodexHookTest(unittest.TestCase):
    def run_hook(
        self,
        command: str,
        *,
        rtk_body: str | None = None,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        workdir: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            if rtk_body is not None:
                rtk = fake_bin / "rtk"
                rtk.write_text(rtk_body, encoding="utf8")
                rtk.chmod(rtk.stat().st_mode | stat.S_IXUSR)

            process_env = {
                **os.environ,
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            }
            for name in BYPASS_ENV:
                process_env.pop(name, None)
            if env:
                process_env.update(env)

            return subprocess.run(
                [str(HOOK)],
                input=payload(command, cwd=cwd, workdir=workdir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                env=process_env,
                timeout=5,
            )

    def assert_no_output(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def rewritten_command(self, result: subprocess.CompletedProcess[str]) -> str:
        self.assertEqual(result.returncode, 0)
        return json.loads(result.stdout)["hookSpecificOutput"]["updatedInput"]["command"]

    def rewritten_input(self, result: subprocess.CompletedProcess[str]) -> dict[str, str]:
        self.assertEqual(result.returncode, 0)
        return json.loads(result.stdout)["hookSpecificOutput"]["updatedInput"]

    def guarded_command_payload(self, command: str) -> str:
        tokens = shlex.split(command)
        self.assertIn(str(OUTPUT_GUARD), tokens)
        index = tokens.index("--b64")
        return base64.b64decode(tokens[index + 1].encode("ascii"), validate=True).decode("utf8")

    def test_rewrites_eligible_command(self) -> None:
        result = self.run_hook(
            "ls -la",
            rtk_body=textwrap.dedent(
                """\
                #!/usr/bin/env sh
                shift
                printf 'rtk %s\\n' "$*"
                """
            ),
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "updatedInput": {"command": "rtk ls -la"},
                }
            },
        )

    def test_accepts_rtk_rewrite_success_code_three(self) -> None:
        result = self.run_hook(
            "pwd",
            rtk_body=textwrap.dedent(
                """\
                #!/usr/bin/env sh
                shift
                printf 'rtk %s\\n' "$*"
                exit 3
                """
            ),
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "updatedInput": {"command": "rtk pwd"},
                }
            },
        )

    def test_rewrites_literal_backslash_n_quotes_and_backslashes(self) -> None:
        for command in [
            r"printf 'literal\nvalue'",
            r"python -c 'print(\"x\\y\")'",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(
                    command,
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\nexit 3\n",
                )

                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    json.loads(result.stdout),
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "updatedInput": {"command": f"rtk {command}"},
                        }
                    },
                )

    def test_passes_through_machine_readable_split_flags(self) -> None:
        for command in [
            "kubectl get pods -o json",
            "kubectl get pods -ojson",
            "kubectl get pods -o=json",
            "kubectl get pods -o jsonpath={.items[*].metadata.name}",
            "kubectl get pods -o=jsonpath={.items[*].metadata.name}",
            "kubectl get pods --output=yaml",
            "aws ec2 describe-instances --output json",
            "fd foo --format json",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(
                    command,
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
                )
                self.assert_no_output(result)

    def test_passes_through_control_rg_files_and_tests(self) -> None:
        for command in [
            "rg --files",
            "rg --json needle",
            "rg -l needle .",
            "rg -L needle .",
            "rg --count needle .",
            "rg --stats needle .",
            "rg --vimgrep needle .",
            "rg --null needle .",
            "rg -0 needle .",
            "rg foo.bar src",
            "rg foo-bar src",
            "rg simpleIdentifier src",
            "grep foo.bar src/app.py",
            "grep foo-bar src/app.py",
            "grep simpleIdentifier src/app.py",
            "grep -c alpha file.txt",
            "grep -l alpha file.txt",
            "grep -q alpha file.txt",
            "grep -cl alpha file.txt",
            "grep -m1 alpha file.txt",
            "grep -m 1 alpha file.txt",
            "grep --max-count 1 alpha file.txt",
            "git status",
            "git status --short",
            "git status -s",
            "git status -sb",
            "git status --branch --short",
            "git status --porcelain",
            "git status --porcelain=v2 -z",
            "git diff --name-only",
            "git diff --name-only -z",
            "git grep CommandRunner",
            "git log --oneline -n 20",
            "git show --name-only --format=",
            "git log --name-only -z",
            "git ls-files -z",
            "jq -r .foo file.json",
            "jq -c . file.json",
            "find . -type f",
            "base64 binary.bin",
            "file binary.bin",
            "hexdump -C binary.bin",
            "xxd binary.bin",
            "cargo test",
            "cargo check",
            "go test ./...",
            "pytest -q",
            "python -m pytest",
            "bun test",
            "make test",
            "make check",
            "make build",
            "make audit-public",
            "make export-public",
            "npm run test",
            "npm run build",
            "npm run lint",
            "pnpm check",
            "pnpm build",
            "yarn test",
            "yarn build",
            "cargo build",
            "go build ./...",
            "mvn test",
            "./mvnw test",
            "mvn dependency:tree",
            "mvn -q dependency:tree",
            "mvn test-compile",
            "gradle test",
            "./gradlew test",
            "./gradlew :app:test",
            "./gradlew :app:build",
            "./gradlew assembleDebug",
            "./gradlew testDebugUnitTest",
            "./gradlew dependencies",
            "./gradlew dependencyInsight",
            "./gradlew tasks",
            "./gradlew projects",
            "./gradlew properties",
            "vitest run",
            "rspec spec",
            "echo hi | cat",
            "echo hi\npwd",
            "sleep 1 & echo done",
            "echo $(pwd)",
            "echo `pwd`",
            "(pwd)",
            "( echo hi )",
            "(cd /tmp; pwd)",
            "cat <(printf hi)",
            "cat <<EOF\nhi\nEOF",
            "echo hi > out.txt",
            "cat < input.txt",
            "true && echo ok",
            "false || echo ok",
            "echo one; echo two",
            "timeout 5 git status",
            "time (pwd)",
            "RTK_DISABLE=1 git status",
            "LC_ALL=C RTK_DISABLE=1 git status",
            "RTK_DISABLED=1 git status",
            "RTK_CODEX_HOOK_DISABLE=1 git status",
            "env RTK_DISABLE=1 git status",
            "env RTK_DISABLED=1 git status",
            "ssh host.example ls",
            "vim file.txt",
            "docker ps",
            "docker compose ps",
            "docker exec -it container sh",
            "podman logs app",
            "kubectl get pods",
            "kubectl exec -it pod -- sh",
            "helm list",
            "systemctl status teledex",
            "journalctl -u teledex -n 50",
            "gh run view",
            "curl -I https://example.com",
            "terraform plan",
            "tofu plan",
            "aws s3 ls",
            "az account show",
            "gcloud projects list",
            "ps aux",
            "ss -tulpn",
            "ip addr",
            "rsync -av src/ host:/tmp/src/",
            "scp file host:/tmp/file",
            "sudo git status",
            "command git status",
            "time git status",
            "stdbuf -oL git status",
            "nice -n 5 git status",
            "ionice -c 3 git status",
            "chronic git status",
            "rg -cl needle .",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(
                    command,
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
                )
                self.assert_no_output(result)

    def test_adapts_exec_command_cmd_shape_and_safe_shell_unwrap(self) -> None:
        result = subprocess.run(
            [str(HOOK)],
            input=payload(
                "bash -lc 'head -n 5 session.jsonl'",
                tool_name="exec_command",
                input_key="cmd",
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=5,
        )
        updated_input = self.rewritten_input(result)
        self.assertEqual(set(updated_input), {"cmd"})
        self.assertEqual(self.guarded_command_payload(updated_input["cmd"]), "head -n 5 session.jsonl")

    def test_safe_shell_unwrap_allows_rtk_rewrite(self) -> None:
        result = self.run_hook(
            "bash -lc 'pwd'",
            rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
        )

        self.assertEqual(self.rewritten_command(result), "rtk pwd")

    def test_passes_through_pitlane_owned_navigation_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf8")
            (root / "hooks").mkdir()
            hook = root / "hooks" / "rtk-codex-hook"
            hook.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf8")
            hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            for command in [
                "cat src/app.py",
                "cat hooks/rtk-codex-hook",
                "head -n 20 src/app.py",
                "head -n20 hooks/rtk-codex-hook",
                "sed -n '1,20p' src/app.py",
                "sed -n '1,20p' hooks/rtk-codex-hook",
                "ls -R src",
                "ls -laR hooks",
                "tree src",
            ]:
                with self.subTest(command=command):
                    result = self.run_hook(
                        command,
                        cwd=root,
                        rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
                    )
                    self.assert_no_output(result)

    def test_only_passes_through_pitlane_owned_source_pipelines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)

            pitlane_owned = [
                "cat src/app.py | head",
                "cat src/app.py | head -n 20",
                "cat src/app.py | head -n20",
                "nl -ba src/app.py | sed -n '1,2p'",
            ]
            unsupported = [
                "cat src/app.py | sed -n p",
                "cat src/app.py | tail -n 20",
                "nl -ba src/app.py | sed -n p",
            ]

            for command in pitlane_owned:
                with self.subTest(command=command):
                    result = self.run_hook(command, cwd=root)
                    self.assert_no_output(result)

            for command in unsupported:
                with self.subTest(command=command):
                    result = self.run_hook(command, cwd=root)
                    self.assertIn(str(OUTPUT_GUARD), self.rewritten_command(result))

    def test_exec_command_workdir_resolves_pitlane_owned_source_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("root guidance\n", encoding="utf8")
            plugin = root / "plugin"
            (plugin / "src").mkdir(parents=True)
            (plugin / "src" / "app.py").write_text(
                "print('ok')\n",
                encoding="utf8",
            )
            subprocess.run(["git", "init", "-q"], cwd=plugin, check=True)

            result = self.run_hook(
                "cat src/app.py | head -n 20",
                workdir=plugin,
            )

        self.assert_no_output(result)

    def test_does_not_treat_extensionless_external_paths_as_pitlane_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            external = Path(tmp) / "external-script"
            external.write_text("#!/usr/bin/env python3\nprint('x' * 10000)\n", encoding="utf8")
            external.chmod(external.stat().st_mode | stat.S_IXUSR)
            external_py = Path(tmp) / "external.py"
            external_py.write_text("print('x' * 10000)\n", encoding="utf8")
            for command in [
                "cat /var/log/syslog | head -n 5",
                "head -n 5 /tmp/data",
                "cat /tmp/config.yaml",
                f"cat {external} | head -n 5",
                f"cat {external_py} | head -n 5",
            ]:
                with self.subTest(command=command):
                    result = self.run_hook(
                        command,
                        rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
                    )
                    if "|" in command:
                        self.assertIn(str(OUTPUT_GUARD), self.rewritten_command(result))
                    else:
                        self.assert_no_output(result)

    def test_public_export_refuses_unsafe_output_paths(self) -> None:
        exporter = PLUGIN_ROOT / "tools" / "export-public-projection.sh"
        if not exporter.exists():
            self.skipTest("private public-projection exporter is not included in the public projection")

        with tempfile.TemporaryDirectory() as tmp:
            cases = {
                "plain": Path(tmp) / "not-public-dist",
                "with-gitignore": Path(tmp) / "with-gitignore",
                "allowed-suffix-with-gitignore": Path(tmp) / "public-dist" / "rtk-codex-plugin",
            }
            for unsafe in cases.values():
                unsafe.mkdir(parents=True)
                (unsafe / "keep.txt").write_text("keep\n", encoding="utf8")
            for unsafe in cases["with-gitignore"], cases["allowed-suffix-with-gitignore"]:
                (unsafe / ".gitignore").write_text("*\n", encoding="utf8")

            for label, unsafe in cases.items():
                with self.subTest(label=label):
                    result = subprocess.run(
                        [str(exporter), str(unsafe)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                        timeout=5,
                    )

                    self.assertEqual(result.returncode, 2)
                    self.assertTrue((unsafe / "keep.txt").exists())

    def test_passes_through_env_prefixed_exact_output_commands(self) -> None:
        for command in [
            "LC_ALL=C rg --files",
            "env LC_ALL=C rg --files",
            "env -i LC_ALL=C rg --files",
            "env -- LC_ALL=C rg --files",
            "LC_ALL=C grep -c alpha file.txt",
            "env LC_ALL=C grep -c alpha file.txt",
            "env -u FOO LC_ALL=C grep -c alpha file.txt",
            "env -uFOO LC_ALL=C grep -c alpha file.txt",
            "env --unset=FOO LC_ALL=C grep -c alpha file.txt",
            "env -C /tmp LC_ALL=C grep -c alpha file.txt",
            "env --chdir=/tmp LC_ALL=C grep -c alpha file.txt",
            "LC_ALL=C git status --short",
            "LC_ALL=C git diff --name-only",
            "env LC_ALL=C jq -c . file.json",
            "stdbuf --output L git status",
            "stdbuf --output=L git status",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(
                    command,
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\nexit 3\n",
                )
                self.assert_no_output(result)

    def test_guards_line_limited_long_line_pipelines_without_rtk(self) -> None:
        for command in [
            "rg session_meta session.jsonl | head -n 5",
            "grep session_meta session.jsonl | tail -n 5",
            "sed -n '1,20p' session.jsonl | head -n 5",
            "codex debug prompt-input | rg -m 3 large-data-inspection",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(command)
                rewritten = self.rewritten_command(result)
                self.assertEqual(self.guarded_command_payload(rewritten), command)

    def test_guards_line_limited_pipelines_with_quoted_shell_metacharacters(self) -> None:
        for command in [
            "grep 'a>b' session.jsonl | head -n 5",
            "grep 'a&&b' session.jsonl | head -n 5",
            "grep 'a;b' session.jsonl | head -n 5",
            "grep 'a<b' session.jsonl | head -n 5",
            "jq '.items[] | select(.x > 1)' session.jsonl | head -n 5",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(command)
                rewritten = self.rewritten_command(result)
                self.assertEqual(self.guarded_command_payload(rewritten), command)

    def test_guards_pipe_ampersand_with_portable_command(self) -> None:
        for command in [
            "grep session_meta session.jsonl |& head -n 5",
            "grep session_meta session.jsonl|& head -n 5",
            "grep session_meta session.jsonl |&head -n 5",
            "grep session_meta session.jsonl|&head -n 5",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(command)
                rewritten = self.rewritten_command(result)
                self.assertEqual(
                    self.guarded_command_payload(rewritten),
                    "grep session_meta session.jsonl 2>&1 | head -n 5",
                )

    def test_pipe_ampersand_normalization_preserves_quoted_literals(self) -> None:
        command = "grep '|&' session.jsonl | head -n 5"
        result = self.run_hook(command)
        rewritten = self.rewritten_command(result)
        self.assertEqual(self.guarded_command_payload(rewritten), command)

    def test_output_guard_runs_normalized_pipe_ampersand_command(self) -> None:
        encoded = base64.b64encode(
            b"python3 -c 'import sys; print(\"out\"); print(\"err\", file=sys.stderr)' 2>&1 | head -n 2"
        ).decode("ascii")
        result = subprocess.run(
            [str(OUTPUT_GUARD), "--b64", encoded],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=5,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("out", result.stdout)
        self.assertIn("err", result.stdout)

    def test_guards_direct_long_line_file_limiters_without_rtk(self) -> None:
        for command in [
            "head -n 5 session.jsonl",
            "env FOO=bar head -n 5 session.jsonl",
            "sudo head -n 5 session.jsonl",
            "sudo env FOO=bar head -n 5 session.jsonl",
            "timeout 5 head -n 5 session.jsonl",
            "timeout -s TERM 5 head -n 5 session.jsonl",
            "env -C/tmp head -n 5 session.jsonl",
            "tail -n 20 teledex.log",
            "sed -n '1,5p' exchange.ndjson",
            "codex debug prompt-input",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(command)
                rewritten = self.rewritten_command(result)
                self.assertEqual(self.guarded_command_payload(rewritten), command)

    def test_explicit_bypass_skips_pretool_output_guard(self) -> None:
        for command in [
            "RTK_CODEX_BYPASS=1 head -n 5 session.jsonl",
            "env RTK_CODEX_BYPASS=1 head -n 5 session.jsonl",
            "env --unset=FOO RTK_CODEX_BYPASS=1 head -n 5 session.jsonl",
            "env -C /tmp RTK_CODEX_BYPASS=1 head -n 5 session.jsonl",
            "env -C/tmp RTK_CODEX_BYPASS=1 head -n 5 session.jsonl",
            "env --chdir=/tmp RTK_CODEX_BYPASS=1 head -n 5 session.jsonl",
            "RTK_CODEX_HOOK_DISABLE=1 head -n 5 session.jsonl",
            "RTK_CODEX_BYPASS=1 grep session_meta session.jsonl | head -n 5",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(command)
                self.assert_no_output(result)

    def test_does_not_guard_non_limited_shell_control_or_plain_text_head(self) -> None:
        for command in [
            "echo hi | cat",
            "rg needle . | wc -l",
            "head -n 5 README.md",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(command)
                self.assert_no_output(result)

    def test_rewrites_safe_transparent_env_prefixes(self) -> None:
        for command, expected in [
            ("FOO=bar pwd", "FOO=bar rtk pwd"),
            ("env FOO=bar pwd", "env FOO=bar rtk pwd"),
            ("env FOO=bar pwd RTK_DISABLE=1", "env FOO=bar rtk pwd RTK_DISABLE=1"),
        ]:
            with self.subTest(command=command):
                result = self.run_hook(
                    command,
                    rtk_body=textwrap.dedent(
                        """\
                        #!/usr/bin/env sh
                        shift
                        case "$1" in
                          "FOO=bar pwd") printf 'FOO=bar rtk pwd\\n' ;;
                          "env FOO=bar pwd") printf 'env FOO=bar rtk pwd\\n' ;;
                          "env FOO=bar pwd RTK_DISABLE=1") printf 'env FOO=bar rtk pwd RTK_DISABLE=1\\n' ;;
                          *) printf 'unexpected command: %s\\n' "$1"; exit 42 ;;
                        esac
                        exit 3
                        """
                    ),
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    json.loads(result.stdout),
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "updatedInput": {"command": expected},
                        }
                    },
                )

    def test_bypass_envs_disable_hook(self) -> None:
        for name in BYPASS_ENV:
            with self.subTest(env=name):
                result = self.run_hook(
                    "ls -la",
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
                    env={name: "1"},
                )
                self.assert_no_output(result)

    def test_legacy_wrapper_bypass_envs_do_not_disable_hook(self) -> None:
        for name in LEGACY_WRAPPER_BYPASS_ENV:
            with self.subTest(env=name):
                result = self.run_hook(
                    "ls -la",
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
                    env={name: "1"},
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    json.loads(result.stdout),
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "updatedInput": {"command": "rtk ls -la"},
                        }
                    },
                )

    def test_failed_rewrite_is_ignored(self) -> None:
        result = self.run_hook(
            "ls -la",
            rtk_body=textwrap.dedent(
                """\
                #!/usr/bin/env sh
                printf 'partial rewrite\\n'
                exit 42
                """
            ),
        )

        self.assert_no_output(result)

    def test_undecodable_rewrite_output_is_ignored(self) -> None:
        result = self.run_hook(
            "ls -la",
            rtk_body="#!/usr/bin/env sh\nshift\nprintf '\\377'\n",
        )

        self.assert_no_output(result)

    def test_binaryish_rewrite_output_is_ignored(self) -> None:
        result = self.run_hook(
            "ls -la",
            rtk_body=(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "sys.stdout.buffer.write(b'rtk ls -la \\x00')\n"
            ),
        )

        self.assert_no_output(result)

    def test_long_rewrite_output_is_ignored(self) -> None:
        result = self.run_hook(
            "ls -la",
            rtk_body=(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "sys.stdout.write('x' * 17000)\n"
            ),
        )

        self.assert_no_output(result)

    def test_output_guard_truncates_long_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "session.jsonl"
            log.write_text(f"session_meta {'x' * 5000}\nshort\n", encoding="utf8")
            encoded = base64.b64encode(f"cat {shlex.quote(str(log))}".encode("utf8")).decode(
                "ascii"
            )

            result = subprocess.run(
                [
                    str(OUTPUT_GUARD),
                    "--b64",
                    encoded,
                    "--max-line-bytes",
                    "64",
                    "--max-output-bytes",
                    "512",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
            )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("[rtk-output-guard: line truncated]", result.stdout)
        self.assertIn("short", result.stdout)
        self.assertIn("full raw output artifact=", result.stdout)
        self.assertIn("bytes=", result.stdout)
        self.assertIn("lines=2", result.stdout)
        self.assertIn("sha256=", result.stdout)

    def test_post_tool_use_compacts_large_human_output_to_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            response = "\n".join(f"line {index} {'x' * 80}" for index in range(220))
            result = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=post_payload("git diff", response),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env={
                    **os.environ,
                    "RTK_CODEX_ARTIFACT_DIR": tmp,
                    "RTK_CODEX_BUDGET_DIR": tmp,
                },
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("[rtk-output-guard: output compacted]", result.stderr)
            self.assertIn("artifact:", result.stderr)
            artifact_line = next(line for line in result.stderr.splitlines() if line.startswith("artifact: "))
            artifact = Path(artifact_line.removeprefix("artifact: "))
            self.assertTrue(artifact.exists())
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(artifact.stat().st_mode), 0o600)

    def test_post_tool_use_preserves_small_machine_readable_output(self) -> None:
        for command in [
            "docker ps",
            "ssh host hostname",
            "git status --short",
            "systemctl status --no-pager -n 5 teledex",
            "rg --json needle",
            "jq . file.json",
            "jq -r .foo file.json",
            "jq -c . file.json",
            "jq --raw-output .foo file.json",
            "jq --compact-output . file.json",
        ]:
            with self.subTest(command=command):
                result = subprocess.run(
                    [str(OUTPUT_POST_HOOK)],
                    input=post_payload(command, "{\"type\":\"match\"}\n"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    timeout=5,
                )

                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_post_tool_use_compacts_large_high_risk_exact_families(self) -> None:
        response = "\n".join(f"line {index} {'x' * 80}" for index in range(220))
        for command in [
            "docker logs app",
            "docker compose logs app",
            "podman logs app",
            "ssh host journalctl -u teledex",
            "ssh host cat /var/log/session.jsonl",
            "jq -r . huge.json",
            "rg --json needle",
            "grep -m1 needle huge.jsonl",
            "git ls-files -z",
            "git diff --name-only",
            "npm install",
            "make test",
            "cargo test",
            "go test ./...",
            "mvn test",
            "./mvnw test",
            "gradle test",
            "./gradlew test",
            "grep needle file | wc -l",
            "rg --files | xargs cat",
            "kubectl get pods -o json",
        ]:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [str(OUTPUT_POST_HOOK)],
                    input=post_payload(command, response),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    timeout=5,
                    env={
                        **os.environ,
                        "RTK_CODEX_ARTIFACT_DIR": tmp,
                        "RTK_CODEX_BUDGET_DIR": tmp,
                    },
                )

                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("output compacted", result.stderr)
                self.assertIn("class:", result.stderr)
                self.assertIn("original_bytes:", result.stderr)
                self.assertIn("original_lines:", result.stderr)
                self.assertIn("artifact:", result.stderr)
                self.assertIn("sha256:", result.stderr)

    def test_post_tool_use_size_aware_summary_does_not_expand_medium_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            response = "x" * 1800
            result = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=post_payload("git diff", response),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env={
                    **os.environ,
                    "RTK_CODEX_ARTIFACT_DIR": tmp,
                    "RTK_CODEX_BUDGET_DIR": tmp,
                    "RTK_CODEX_HUMAN_OUTPUT_BYTES": "1024",
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertLess(len(result.stderr.encode("utf8")), len(response.encode("utf8")))

    def test_post_tool_use_removes_artifact_when_summary_would_expand_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            response = "x\n" * 301
            result = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=post_payload("echo many-lines", response),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env={
                    **os.environ,
                    "RTK_CODEX_ARTIFACT_DIR": tmp,
                    "RTK_CODEX_BUDGET_DIR": tmp,
                    "RTK_CODEX_VISIBLE_OUTPUT_LINES": "20",
                },
            )

            artifacts = [path for path in Path(tmp).rglob("*") if path.is_file()]

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertEqual(artifacts, [])

    def test_post_tool_use_line_count_metadata_handles_trailing_newline(self) -> None:
        cases = {
            "line\n" * 1100: "original_lines: 1100",
            ("line\n" * 1099) + "line": "original_lines: 1100",
        }
        for response, expected in cases.items():
            with self.subTest(response=response), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [str(OUTPUT_POST_HOOK)],
                    input=post_payload("git diff", response),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    timeout=5,
                    env={
                        **os.environ,
                        "RTK_CODEX_ARTIFACT_DIR": tmp,
                        "RTK_CODEX_BUDGET_DIR": tmp,
                        "RTK_CODEX_VISIBLE_OUTPUT_LINES": "1",
                    },
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn(expected, result.stderr)
                self.assertNotIn("original_lines: 1101", result.stderr)

    def test_post_tool_use_ignores_empty_redirected_output(self) -> None:
        result = subprocess.run(
            [str(OUTPUT_POST_HOOK)],
            input=post_payload("jq . huge.json > out.json", ""),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=5,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_post_tool_use_wrappers_use_inner_command_class(self) -> None:
        for command in [
            "timeout 5 docker logs app",
            "timeout -s TERM 5 docker logs app",
            "sudo --user root docker logs app",
            "time -o /tmp/rtk-time.txt docker logs app",
            "env --unset=FOO docker logs app",
            "env -uFOO docker logs app",
            "stdbuf --output L docker logs app",
            "stdbuf --output=L docker logs app",
        ]:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [str(OUTPUT_POST_HOOK)],
                    input=post_payload(command, "log\n" * 1400),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    timeout=5,
                    env={
                        **os.environ,
                        "RTK_CODEX_ARTIFACT_DIR": tmp,
                        "RTK_CODEX_BUDGET_DIR": tmp,
                        "RTK_CODEX_AGGREGATE_VISIBLE_OUTPUT_BYTES": "0",
                        "RTK_CODEX_VISIBLE_OUTPUT_BYTES": "50000",
                        "RTK_CODEX_HUMAN_OUTPUT_BYTES": "5120",
                    },
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn("class: container-log-or-dump", result.stderr)

    def test_post_tool_use_compacts_jq_pipeline_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=post_payload("jq . file.json | tail -n 200", "value\n" * 1400),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env={
                    **os.environ,
                    "RTK_CODEX_ARTIFACT_DIR": tmp,
                    "RTK_CODEX_BUDGET_DIR": tmp,
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("output compacted", result.stderr)

    def test_post_tool_use_compacts_parallel_wrapper_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "multi_tool_use.parallel",
                        "session_id": "session-1",
                        "turn_id": "turn-parallel",
                        "tool_use_id": "tool-parallel",
                        "tool_input": {
                            "tool_uses": [
                                {"recipient_name": "functions.exec_command", "parameters": {"cmd": "git diff"}}
                            ]
                        },
                        "tool_response": "parallel output\n" * 700,
                    }
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env={
                    **os.environ,
                    "RTK_CODEX_ARTIFACT_DIR": tmp,
                    "RTK_CODEX_BUDGET_DIR": tmp,
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("tool: multi_tool_use.parallel", result.stderr)
        self.assertIn("output compacted", result.stderr)

    def test_post_tool_use_compacts_write_stdin_output_with_original_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "write_stdin",
                        "session_id": "session-1",
                        "turn_id": "turn-write",
                        "tool_use_id": "tool-write",
                        "tool_input": {"command": "python -c 'print(1)'"},
                        "tool_response": "chunk\n" * 2000,
                    }
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env={
                    **os.environ,
                    "RTK_CODEX_ARTIFACT_DIR": tmp,
                    "RTK_CODEX_BUDGET_DIR": tmp,
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("tool: write_stdin", result.stderr)
        self.assertIn("output compacted", result.stderr)

    def test_post_tool_use_compacts_raw_write_stdin_without_original_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "write_stdin",
                        "session_id": "session-1",
                        "turn_id": "turn-write",
                        "tool_use_id": "tool-write",
                        "tool_input": {"session_id": "exec-session"},
                        "tool_response": "chunk\n" * 2000,
                    }
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env={
                    **os.environ,
                    "RTK_CODEX_ARTIFACT_DIR": tmp,
                    "RTK_CODEX_BUDGET_DIR": tmp,
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("tool: write_stdin", result.stderr)
        self.assertIn("write_stdin session_id=exec-session", result.stderr)
        self.assertIn("output compacted", result.stderr)

    def test_post_tool_use_applies_turn_aggregate_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                **os.environ,
                "RTK_CODEX_ARTIFACT_DIR": tmp,
                "RTK_CODEX_BUDGET_DIR": tmp,
                "RTK_CODEX_AGGREGATE_VISIBLE_OUTPUT_BYTES": "2000",
                "RTK_CODEX_VISIBLE_OUTPUT_BYTES": "50000",
                "RTK_CODEX_HUMAN_OUTPUT_BYTES": "50000",
            }
            first = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=post_payload("echo first", "a" * 1500, turn_id="turn-aggregate"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env=env,
            )
            second = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=post_payload("echo second", "b" * 900, turn_id="turn-aggregate"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env=env,
            )
            budget = json.loads((Path(tmp) / "session-1-turn-aggregate.json").read_text(encoding="utf8"))

        self.assertEqual(first.returncode, 0)
        self.assertEqual(first.stdout, "")
        self.assertEqual(second.returncode, 2)
        self.assertEqual(second.stdout, "")
        self.assertIn("turn aggregate visible output budget exceeded 2000 bytes", second.stderr)
        self.assertEqual(budget["visible_bytes"], 1500 + len(second.stderr.encode("utf8")))

    def test_post_tool_use_honors_nonleading_bypass_assignment(self) -> None:
        result = subprocess.run(
            [str(OUTPUT_POST_HOOK)],
            input=post_payload("LC_ALL=C RTK_CODEX_BYPASS=1 git diff", "diff\n" * 3000),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=5,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_post_tool_use_rejects_argument_position_bypass_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=post_payload("env FOO=bar cmd RTK_CODEX_BYPASS=1", "diff\n" * 3000),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env={
                    **os.environ,
                    "RTK_CODEX_ARTIFACT_DIR": tmp,
                    "RTK_CODEX_BUDGET_DIR": tmp,
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("output compacted", result.stderr)

    def test_post_tool_use_honors_bypass_after_wrappers(self) -> None:
        for command in [
            "timeout 5 env RTK_CODEX_BYPASS=1 docker logs app",
            "env --unset=FOO RTK_CODEX_BYPASS=1 docker logs app",
            "env -C /tmp RTK_CODEX_BYPASS=1 docker logs app",
            "env -C/tmp RTK_CODEX_BYPASS=1 docker logs app",
            "env --chdir=/tmp RTK_CODEX_BYPASS=1 docker logs app",
        ]:
            with self.subTest(command=command):
                result = subprocess.run(
                    [str(OUTPUT_POST_HOOK)],
                    input=post_payload(command, "diff\n" * 3000),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    timeout=5,
                )

                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_post_tool_use_honors_bypass_for_stream_and_parallel_wrappers(self) -> None:
        write_result = subprocess.run(
            [str(OUTPUT_POST_HOOK)],
            input=json.dumps(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "write_stdin",
                    "session_id": "session-1",
                    "turn_id": "turn-write",
                    "tool_use_id": "tool-write",
                    "tool_input": {"command": "RTK_CODEX_BYPASS=1 python emit.py"},
                    "tool_response": "chunk\n" * 3000,
                }
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=5,
        )
        parallel_result = subprocess.run(
            [str(OUTPUT_POST_HOOK)],
            input=json.dumps(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "multi_tool_use.parallel",
                    "session_id": "session-1",
                    "turn_id": "turn-parallel",
                    "tool_use_id": "tool-parallel",
                    "tool_input": {
                        "tool_uses": [
                            {
                                "recipient_name": "functions.exec_command",
                                "parameters": {"cmd": "RTK_CODEX_BYPASS=1 jq . huge.json"},
                            }
                        ]
                    },
                    "tool_response": "chunk\n" * 3000,
                }
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=5,
        )
        parallel_shell_result = subprocess.run(
            [str(OUTPUT_POST_HOOK)],
            input=json.dumps(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "multi_tool_use.parallel",
                    "session_id": "session-1",
                    "turn_id": "turn-parallel",
                    "tool_use_id": "tool-parallel-shell",
                    "tool_input": {
                        "tool_uses": [
                            {
                                "recipient_name": "functions.exec_command",
                                "parameters": {"cmd": "bash -lc 'RTK_CODEX_BYPASS=1 jq . huge.json'"},
                            },
                            {
                                "recipient_name": "functions.exec_command",
                                "parameters": {"cmd": "sh -lc 'RTK_CODEX_BYPASS=1 docker logs app'"},
                            },
                        ]
                    },
                    "tool_response": "chunk\n" * 3000,
                }
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=5,
        )

        for result in [write_result, parallel_result, parallel_shell_result]:
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")

    def test_post_tool_use_stream_bypass_marker_matches_real_write_stdin_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                **os.environ,
                "RTK_CODEX_ARTIFACT_DIR": tmp,
                "RTK_CODEX_BUDGET_DIR": tmp,
            }
            start = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "write_stdin",
                        "session_id": "session-1",
                        "turn_id": "turn-write",
                        "tool_use_id": "tool-write-start",
                        "tool_input": {
                            "session_id": "pty-1",
                            "command": "RTK_CODEX_BYPASS=1 python emit.py",
                        },
                        "tool_response": "chunk\n" * 3000,
                    }
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env=env,
            )
            followup = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "write_stdin",
                        "session_id": "session-1",
                        "turn_id": "turn-write",
                        "tool_use_id": "tool-write-followup",
                        "tool_input": {"session_id": "pty-1"},
                        "tool_response": "chunk\n" * 3000,
                    }
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env=env,
            )
            exec_start = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "functions.exec_command",
                        "session_id": "session-1",
                        "turn_id": "turn-write",
                        "tool_use_id": "tool-exec-start",
                        "tool_input": {"cmd": "RTK_CODEX_BYPASS=1 python emit.py"},
                        "tool_response": "Process running with session ID pty-2\n",
                    }
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env=env,
            )
            exec_followup = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "functions.write_stdin",
                        "session_id": "session-1",
                        "turn_id": "turn-write",
                        "tool_use_id": "tool-exec-followup",
                        "tool_input": {"session_id": "pty-2"},
                        "tool_response": "chunk\n" * 3000,
                    }
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env=env,
            )

        for result in [start, followup, exec_start, exec_followup]:
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")

    def test_post_tool_use_compacts_mixed_parallel_bypass_children(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "multi_tool_use.parallel",
                        "session_id": "session-1",
                        "turn_id": "turn-parallel",
                        "tool_use_id": "tool-parallel",
                        "tool_input": {
                            "tool_uses": [
                                {
                                    "recipient_name": "functions.exec_command",
                                    "parameters": {"cmd": "bash -lc 'RTK_CODEX_BYPASS=1 jq . huge.json'"},
                                },
                                {
                                    "recipient_name": "functions.exec_command",
                                    "parameters": {"cmd": "docker logs app"},
                                },
                            ]
                        },
                        "tool_response": "chunk\n" * 3000,
                    }
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env={
                    **os.environ,
                    "RTK_CODEX_ARTIFACT_DIR": tmp,
                    "RTK_CODEX_BUDGET_DIR": tmp,
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("output compacted", result.stderr)

    def test_post_tool_use_compacts_parallel_with_non_command_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "multi_tool_use.parallel",
                        "session_id": "session-1",
                        "turn_id": "turn-parallel",
                        "tool_use_id": "tool-parallel",
                        "tool_input": {
                            "tool_uses": [
                                {
                                    "recipient_name": "functions.exec_command",
                                    "parameters": {"cmd": "RTK_CODEX_BYPASS=1 jq . huge.json"},
                                },
                                {
                                    "recipient_name": "mcp__requests.fetch",
                                    "parameters": {"url": "https://example.com"},
                                },
                            ]
                        },
                        "tool_response": "chunk\n" * 3000,
                    }
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env={
                    **os.environ,
                    "RTK_CODEX_ARTIFACT_DIR": tmp,
                    "RTK_CODEX_BUDGET_DIR": tmp,
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("output compacted", result.stderr)

    def test_post_tool_use_compacts_parallel_with_non_exec_command_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [str(OUTPUT_POST_HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "multi_tool_use.parallel",
                        "session_id": "session-1",
                        "turn_id": "turn-parallel",
                        "tool_use_id": "tool-parallel",
                        "tool_input": {
                            "tool_uses": [
                                {
                                    "recipient_name": "mcp__docker.run_command",
                                    "parameters": {"command": "RTK_CODEX_BYPASS=1 docker logs app"},
                                }
                            ]
                        },
                        "tool_response": "chunk\n" * 3000,
                    }
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
                env={
                    **os.environ,
                    "RTK_CODEX_ARTIFACT_DIR": tmp,
                    "RTK_CODEX_BUDGET_DIR": tmp,
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("output compacted", result.stderr)


if __name__ == "__main__":
    unittest.main()
