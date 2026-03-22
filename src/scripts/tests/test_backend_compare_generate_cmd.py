#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_opentitan_tlul_slice_backend_compare.py"


def _load_module():
    module_dir = str(MODULE_PATH.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location("backend_compare_runner", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BackendCompareGenerateCmdTest(unittest.TestCase):
    def test_generate_cmd_emits_raw_cuda_sidecars(self) -> None:
        if not MODULE_PATH.is_file():
            self.skipTest(f"Module not available: {MODULE_PATH.name}")
        module = _load_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            generated_root = root / "generated"
            compare_root = root / "compare"
            generated_root.mkdir()
            compare_root.mkdir()
            manifest = generated_root / "generated_dir_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "opentitan-tlul-slice-generated-dirs-v1",
                        "rows": [
                            {
                                "slice_name": "edn_main_sm",
                                "status": "completed",
                                "fused_dir": str(generated_root / "edn_main_sm" / "fused"),
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            commands: list[list[str]] = []

            def fake_run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> None:
                commands.append(list(cmd))
                if str(module.GENERATE_SCRIPT) in cmd:
                    return
                if str(module.PREPARE_PLAN_SCRIPT) in cmd:
                    (compare_root / "backend_compare_plan.json").write_text(
                        json.dumps({"rows": [], "schema_version": "opentitan-tlul-slice-backend-compare-v1"}) + "\n",
                        encoding="utf-8",
                    )
                    return

            module.subprocess.run = fake_run  # type: ignore[assignment]
            module._load_json = lambda path: json.loads(path.read_text())  # type: ignore[assignment]
            rc = module.main(
                [
                    "--slice",
                    "edn_main_sm",
                    "--generated-root",
                    str(generated_root),
                    "--compare-root",
                    str(compare_root),
                    "--summary-json",
                    str(root / "summary.json"),
                    "--summary-md",
                    str(root / "summary.md"),
                ]
            )
            self.assertEqual(rc, 0)
            generate_cmd = next(cmd for cmd in commands if str(module.GENERATE_SCRIPT) in cmd)
            self.assertIn("--emit-raw-cuda-sidecars", generate_cmd)


if __name__ == "__main__":
    unittest.main()
