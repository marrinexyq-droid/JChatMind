import importlib.util
import unittest
from pathlib import Path


SCANNER = Path(__file__).resolve().parents[1] / "check_secrets.py"


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

    def test_accepts_tracked_files_without_forbidden_values(self) -> None:
        scanner = self._load_scanner()
        self.assertTrue(hasattr(scanner, "scan_text"), "scanner must expose scan_text")

        violations = scanner.scan_text(Path("config.txt"), "password: ${DB_PASSWORD}\n")

        self.assertEqual(violations, [])

    def _load_scanner(self):
        self.assertTrue(SCANNER.is_file(), "check_secrets.py must exist")
        spec = importlib.util.spec_from_file_location("check_secrets", SCANNER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


if __name__ == "__main__":
    unittest.main()
