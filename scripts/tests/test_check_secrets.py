import ast
import contextlib
import importlib.util
import inspect
import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCANNER = Path(__file__).resolve().parents[1] / "check_secrets.py"
REPOSITORY = SCANNER.parents[1]
SECRET_WORKFLOW = REPOSITORY / ".github" / "workflows" / "secret-check.yml"
SECURE_CONFIGS = (
    REPOSITORY / "jchatmind" / "reranker-service" / "rag_eval" / "config.py",
    REPOSITORY / "计划文档" / "rag_eval" / "config.py",
)


class CheckSecretsTest(unittest.TestCase):

    def test_scanner_exists(self) -> None:
        self.assertTrue(SCANNER.is_file(), "check_secrets.py must exist")

    def test_reports_only_path_and_line_for_forbidden_values(self) -> None:
        scanner = self._load_scanner()
        secret_default = "${DB_" + "PASSWORD:not-a-real-password}"
        api_key = "sk-" + "x" * 20
        self.assertTrue(hasattr(scanner, "scan_text"), "scanner must expose scan_text")

        violations = scanner.scan_text(
            Path("config.txt"),
            f"password: {secret_default}\napi-key: {api_key}\n",
        )

        self.assertEqual(violations, ["config.txt:1", "config.txt:2"])
        self.assertNotIn(secret_default, "\n".join(violations))
        self.assertNotIn(api_key, "\n".join(violations))

    def test_detects_provider_tokens_and_secret_getenv_defaults(self) -> None:
        scanner = self._load_scanner()
        provider_token = "a" * 32 + "." + "b" * 16
        getenv_default = (
            "ZHIPUAI_API_KEY = os." + "getenv(\"ZHIPUAI_API_KEY\", \"" + provider_token + "\")"
        )

        violations = scanner.scan_text(
            Path("config.py"),
            f"provider_key = \"{provider_token}\"\n{getenv_default}\n",
        )

        self.assertEqual(violations, ["config.py:1", "config.py:2"])
        output = "\n".join(violations)
        self.assertNotIn(provider_token, output)

    def test_scoped_configs_use_secret_environment_variables_without_defaults(self) -> None:
        expected_variables = {"DB_PASSWORD", "ZHIPUAI_API_KEY"}
        for config_path in SECURE_CONFIGS:
            tree = ast.parse(config_path.read_text(encoding="utf-8"))
            found_variables: set[str] = set()
            for node in ast.walk(tree):
                if not self._is_os_getenv_call(node):
                    continue
                variable = node.args[0].value
                if variable not in expected_variables:
                    continue
                found_variables.add(variable)
                self.assertEqual(
                    len(node.args),
                    1,
                    f"{config_path.as_posix()}:{node.lineno} {variable} must not have a default",
                )
            self.assertEqual(found_variables, expected_variables)

    def test_accepts_tracked_files_without_forbidden_values(self) -> None:
        scanner = self._load_scanner()
        self.assertTrue(hasattr(scanner, "scan_text"), "scanner must expose scan_text")

        violations = scanner.scan_text(Path("config.txt"), "password: ${DB_PASSWORD}\n")

        self.assertEqual(violations, [])

    def test_read_failure_is_reported_without_file_content(self) -> None:
        scanner = self._load_scanner()
        missing_path = Path("missing-secret.txt")

        records = scanner.scan_paths([missing_path], REPOSITORY)

        self.assertEqual(records, ["missing-secret.txt:read-error"])

    def test_repository_root_is_resolved_from_a_subdirectory(self) -> None:
        scanner = self._load_scanner()
        self.assertTrue(hasattr(scanner, "repository_root"), "scanner must resolve the repository root")

        root = scanner.repository_root(REPOSITORY / "scripts")

        self.assertEqual(root.resolve(), REPOSITORY.resolve())

    def test_tracked_enumeration_is_rooted_at_the_repository(self) -> None:
        scanner = self._load_scanner()
        self.assertEqual(list(inspect.signature(scanner.tracked_paths).parameters), ["root"])

        paths = scanner.tracked_paths(REPOSITORY)

        self.assertIn(Path("scripts/check_secrets.py"), paths)
        self.assertIn(Path("计划文档/rag_eval/config.py"), paths)

    def test_cli_reports_findings_with_exit_one(self) -> None:
        scanner = self._load_scanner()
        stdout = io.StringIO()
        with (
            patch.object(scanner, "repository_root", return_value=REPOSITORY, create=True),
            patch.object(scanner, "tracked_paths", return_value=[Path("config.py")]),
            patch.object(scanner, "scan_paths", return_value=["config.py:7"]),
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = scanner.main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "config.py:7\n")

    def test_cli_fails_closed_when_a_tracked_file_cannot_be_read(self) -> None:
        scanner = self._load_scanner()
        stdout = io.StringIO()
        with (
            patch.object(scanner, "repository_root", return_value=REPOSITORY, create=True),
            patch.object(scanner, "tracked_paths", return_value=[Path("missing-secret.txt")]),
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = scanner.main()

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "missing-secret.txt:read-error\n")

    def test_cli_fails_closed_when_tracked_enumeration_fails(self) -> None:
        scanner = self._load_scanner()
        stdout = io.StringIO()
        with (
            patch.object(scanner, "repository_root", return_value=REPOSITORY, create=True),
            patch.object(scanner, "tracked_paths", side_effect=RuntimeError),
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = scanner.main()

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), ".:tracked-enumeration-error\n")

    def test_cli_scans_the_full_repository_when_run_from_a_subdirectory(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCANNER)],
            cwd=REPOSITORY / "scripts",
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_dedicated_secret_workflow_has_no_path_filter(self) -> None:
        self.assertTrue(SECRET_WORKFLOW.is_file(), "secret-check.yml must exist")
        workflow = SECRET_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request:", workflow)
        self.assertIn("push:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("python scripts/check_secrets.py", workflow)
        self.assertNotIn("paths:", workflow)

    def _load_scanner(self):
        self.assertTrue(SCANNER.is_file(), "check_secrets.py must exist")
        spec = importlib.util.spec_from_file_location("check_secrets", SCANNER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _is_os_getenv_call(self, node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "os"
            and node.func.attr == "getenv"
            and bool(node.args)
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        )


if __name__ == "__main__":
    unittest.main()
