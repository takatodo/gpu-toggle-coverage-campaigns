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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "trace_vl_field_writers.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TraceVlFieldWritersTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("trace_vl_field_writers_test", MODULE_PATH)

    def test_trace_field_writers_groups_direct_and_delayed_sites(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            cpp = mdir / "Vdemo___024root__0.cpp"
            cpp.write_text(
                "\n".join(
                    [
                        "void Vdemo___024root___nba_comb__TOP__0(Vdemo___024root* vlSelf) {",
                        "  vlSelf->demo__DOT__field_q = 1U;",
                        "}",
                        "void Vdemo___024root___nba_sequent__TOP__0(Vdemo___024root* vlSelf) {",
                        "  __Vdly__demo__DOT__field_q = 0U;",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = self.module.trace_field_writers(mdir, ["demo__DOT__field_q"])
            field = summary["fields"]["demo__DOT__field_q"]

            self.assertEqual(field["writer_count"], 2)
            self.assertEqual(field["phase_summary"]["nba_comb"], 1)
            self.assertEqual(field["phase_summary"]["nba_sequent"], 1)
            self.assertEqual(field["writers"][0]["kind"], "direct")
            self.assertEqual(field["writers"][1]["kind"], "delayed")

    def test_trace_field_writers_handles_multiline_assignment_lhs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            cpp = mdir / "Vdemo___024root__0.cpp"
            cpp.write_text(
                "\n".join(
                    [
                        "void Vdemo___024root___nba_comb__TOP__0(Vdemo___024root* vlSelf) {",
                        "  vlSelf->demo__DOT__wide_q[0U]",
                        "      = 42U;",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = self.module.trace_field_writers(mdir, ["demo__DOT__wide_q"])
            field = summary["fields"]["demo__DOT__wide_q"]

            self.assertEqual(field["writer_count"], 1)
            self.assertEqual(field["writers"][0]["line"], 2)
            self.assertEqual(field["writers"][0]["phase"], "nba_comb")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir) / "mdir"
            mdir.mkdir()
            (mdir / "Vdemo___024root__0.cpp").write_text(
                "\n".join(
                    [
                        "void Vdemo___024root___nba_comb__TOP__0(Vdemo___024root* vlSelf) {",
                        "  vlSelf->demo__DOT__field_q = 1U;",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            json_out = Path(tmpdir) / "trace.json"
            argv = [
                "trace_vl_field_writers.py",
                str(mdir),
                "demo__DOT__field_q",
                "--json-out",
                str(json_out),
            ]

            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["fields"]["demo__DOT__field_q"]["writer_count"], 1)


if __name__ == "__main__":
    unittest.main()
