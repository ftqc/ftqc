import json
import subprocess
import sys
import unittest


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "ftqc", *args],
                              text=True, capture_output=True)

    def test_json_comparison(self):
        result = self.run_cli("--logical-qubits", "100", "--logical-steps", "1000000",
                              "--physical-error-rate", "0.001", "0.0001", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        reports = json.loads(result.stdout)
        self.assertEqual([r["code_distance"] for r in reports], [21, 9])
        self.assertEqual(reports[0]["physical_qubits"], 88200)
        self.assertAlmostEqual(reports[0]["runtime_seconds"], 21)

    def test_text_contains_assumptions(self):
        result = self.run_cli("--logical-qubits", "1", "--logical-steps", "1",
                              "--physical-error-rate", "0.001")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Excludes magic-state factories", result.stdout)

    def test_invalid_input_is_clean_error(self):
        for rate in ["0.01", "nan", "0"]:
            result = self.run_cli("--logical-qubits", "1", "--logical-steps", "1",
                                  "--physical-error-rate", rate)
            self.assertEqual(result.returncode, 2)
            self.assertIn("error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_version_and_help(self):
        self.assertIn("0.1.0", self.run_cli("--version").stdout)
        self.assertEqual(self.run_cli("--help").returncode, 0)
