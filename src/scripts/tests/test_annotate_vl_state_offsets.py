#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "annotate_vl_state_offsets.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AnnotateVlStateOffsetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("annotate_vl_state_offsets_test", MODULE_PATH)

    def test_direct_offsets_emit_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            out = root / "annotations.json"

            def _fake_annotate(_layout, offset):
                mapping = {
                    483: {
                        "field_name": "__VicoPhaseResult",
                        "field_offset": 483,
                        "field_size": 1,
                        "field_byte_offset": 0,
                    },
                    5912: {
                        "field_name": "vlSymsp",
                        "field_offset": 5912,
                        "field_size": 8,
                        "field_byte_offset": 0,
                    },
                }
                return mapping.get(offset)

            argv = [
                "annotate_vl_state_offsets.py",
                str(mdir),
                "483",
                "5912",
                "--json-out",
                str(out),
            ]
            with mock.patch.object(self.module.cmp, "probe_root_layout", return_value=[]):
                with mock.patch.object(self.module.cmp, "annotate_state_offset", side_effect=_fake_annotate):
                    with mock.patch.object(sys, "argv", argv):
                        self.module.main()

            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["offsets"], [483, 5912])
            self.assertTrue(payload["all_offsets_annotated"])
            self.assertTrue(payload["all_offsets_internal_only"])
            self.assertEqual(payload["role_summary"], {"verilator_internal": 2})

    def test_summary_offsets_can_target_gpu_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            out = root / "annotations.json"
            summary = root / "summary.json"
            summary.write_text(
                json.dumps(
                    {
                        "state_delta": {"first_changed_offsets": [1]},
                        "gpu_runs": [
                            {"delta_from_host_probe": {"first_changed_offsets": [7, 8]}},
                            {"delta_from_host_probe": {"first_changed_offsets": [9]}},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            def _fake_annotate(_layout, offset):
                return {
                    "field_name": f"demo__DOT__field_{offset}",
                    "field_offset": offset,
                    "field_size": 1,
                    "field_byte_offset": 0,
                }

            argv = [
                "annotate_vl_state_offsets.py",
                str(mdir),
                "--summary",
                str(summary),
                "--gpu-run-index",
                "1",
                "--json-out",
                str(out),
            ]
            with mock.patch.object(self.module.cmp, "probe_root_layout", return_value=[]):
                with mock.patch.object(self.module.cmp, "annotate_state_offset", side_effect=_fake_annotate):
                    with mock.patch.object(sys, "argv", argv):
                        self.module.main()

            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["offsets"], [7, 8])
            self.assertEqual(payload["summary_source"]["gpu_run_index"], 1)
            self.assertEqual(payload["summary_source"]["delta_key"], "delta_from_host_probe")
            self.assertFalse(payload["all_offsets_internal_only"])
            self.assertEqual(payload["role_summary"], {"design_state": 2})


if __name__ == "__main__":
    unittest.main()
