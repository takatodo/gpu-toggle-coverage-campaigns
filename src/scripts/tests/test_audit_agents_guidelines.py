#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_agents_guidelines.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditAgentsGuidelinesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_agents_guidelines_test", MODULE_PATH)

    def _write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_main_emits_quantitative_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write(root / "AGENTS.md", "# AGENTS\n")
            self._write(root / "README.md", "Use run_good.py in docs.\n")
            self._write(root / "docs" / "guide.md", "run_good.py is documented here.\n")
            self._write(root / "helper.py", "print('root helper')\n")
            self._write(
                root / "src" / "tools" / "run_good.py",
                'def main():\n    return 0\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n',
            )
            self._write(
                root / "src" / "tools" / "misc.py",
                'def main():\n    return 0\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n',
            )
            large_body = (
                "def main():\n"
                + "".join("    x = 1\n" for _ in range(301))
                + '\nif __name__ == "__main__":\n    raise SystemExit(main())\n'
            )
            self._write(root / "src" / "runners" / "run_big.py", large_body)
            self._write(root / "src" / "scripts" / "tests" / "test_run_good.py", "def test_ok():\n    pass\n")

            json_out = root / "work" / "agents_guideline_audit.json"
            rc = self.module.main(["--repo-root", str(root), "--json-out", str(json_out)])

            self.assertEqual(rc, 1)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["scope"], "agents_guideline_audit")
            self.assertEqual(payload["summary"]["repo_root_python_file_count"], 1)
            self.assertEqual(payload["summary"]["banned_python_filename_count"], 1)
            self.assertEqual(payload["summary"]["total_cli_files"], 3)
            self.assertEqual(payload["summary"]["cli_with_matching_test_count"], 1)
            self.assertAlmostEqual(payload["summary"]["cli_with_matching_test_ratio"], 1 / 3)
            self.assertEqual(payload["summary"]["cli_with_doc_mention_count"], 1)
            self.assertAlmostEqual(payload["summary"]["cli_with_doc_mention_ratio"], 1 / 3)
            self.assertEqual(payload["summary"]["cli_over_300_loc_count"], 1)
            self.assertEqual(payload["summary"]["cli_over_500_loc_count"], 0)
            self.assertFalse(payload["summary"]["hard_gate_passed"])
            self.assertEqual(payload["hard_gates"]["repo_root_python_files_zero"]["violations"], ["helper.py"])
            self.assertEqual(payload["hard_gates"]["banned_python_filenames_zero"]["violations"], ["src/tools/misc.py"])
            self.assertIn("src/runners/run_big.py", payload["top_debt_lists"]["over_300_loc"])
            self.assertIn("src/runners/run_big.py", payload["top_debt_lists"]["missing_tests"])
            self.assertIn("src/tools/misc.py", payload["top_debt_lists"]["missing_doc_mentions"])

    def test_contract_suffix_tests_count_as_matching_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write(root / "AGENTS.md", "# AGENTS\n")
            self._write(root / "README.md", "run_probe.py\n")
            self._write(
                root / "src" / "tools" / "run_probe.py",
                'def main():\n    return 0\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n',
            )
            self._write(root / "src" / "scripts" / "tests" / "test_run_probe_contract.py", "def test_ok():\n    pass\n")

            json_out = root / "agents.json"
            rc = self.module.main(["--repo-root", str(root), "--json-out", str(json_out)])

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            row = payload["cli_rows"][0]
            self.assertTrue(row["has_matching_test"])
            self.assertEqual(row["matching_test_count"], 1)
            self.assertEqual(row["matching_test_paths"], ["src/scripts/tests/test_run_probe_contract.py"])

    def test_main_returns_zero_for_clean_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write(root / "AGENTS.md", "# AGENTS\n")
            self._write(root / "README.md", "run_clean.py\nrun_clean_runner.py\n")
            self._write(
                root / "src" / "tools" / "run_clean.py",
                'def main():\n    return 0\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n',
            )
            self._write(
                root / "src" / "runners" / "run_clean_runner.py",
                'def main():\n    return 0\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n',
            )
            self._write(root / "src" / "scripts" / "tests" / "test_run_clean.py", "def test_ok():\n    pass\n")
            self._write(root / "src" / "scripts" / "tests" / "test_run_clean_runner.py", "def test_ok():\n    pass\n")

            json_out = root / "agents.json"
            rc = self.module.main(["--repo-root", str(root), "--json-out", str(json_out)])

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertTrue(payload["summary"]["hard_gate_passed"])
            self.assertEqual(payload["summary"]["repo_root_python_file_count"], 0)
            self.assertEqual(payload["summary"]["banned_python_filename_count"], 0)
            self.assertEqual(payload["summary"]["cli_with_matching_test_ratio"], 1.0)
            self.assertEqual(payload["summary"]["cli_with_doc_mention_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
