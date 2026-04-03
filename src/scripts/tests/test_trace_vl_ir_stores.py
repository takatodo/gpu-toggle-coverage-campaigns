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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "trace_vl_ir_stores.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TraceVlIrStoresTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("trace_vl_ir_stores_test", MODULE_PATH)

    def test_trace_function_stores_maps_root_geps_back_to_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            (mdir / "Vdemo___024root.h").write_text(
                "\n".join(
                    [
                        "class Vdemo__Syms;",
                        "class Vdemo___024root final {",
                        "  public:",
                        "    struct {",
                        "      CData/*0:0*/ demo__DOT__flag_q;",
                        "      VL_OUT(toggle_bitmap_word2_o,31,0);",
                        "    };",
                        "    struct {",
                        "      VlWide<3>/*65:0*/ demo__DOT__tl_h_o;",
                        "    };",
                        "};",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (mdir / "Vdemo___024root__0.ll").write_text(
                "\n".join(
                    [
                        "define dso_local void @demo_func(ptr %0) {",
                        "  %1 = getelementptr inbounds %class.Vdemo___024root, ptr %0, i64 0, i32 0, i32 1",
                        "  store i32 7, ptr %1, align 4",
                        "  %2 = getelementptr inbounds %class.Vdemo___024root, ptr %0, i64 0, i32 1, i32 0",
                        "  %3 = getelementptr inbounds [3 x i32], ptr %2, i64 0, i64 2",
                        "  store i32 9, ptr %3, align 4",
                        "  ret void",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.trace_function_stores(mdir, ["demo_func"])
            func = payload["functions"]["demo_func"]

            self.assertEqual(func["store_count"], 2)
            self.assertEqual(func["field_summary"]["toggle_bitmap_word2_o"]["store_count"], 1)
            self.assertEqual(func["field_summary"]["demo__DOT__tl_h_o"]["store_count"], 1)
            self.assertEqual(func["stores"][1]["element_path"], "[2]")

    def test_trace_function_stores_marks_dynamic_indices(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            (mdir / "Vdemo___024root.h").write_text(
                "\n".join(
                    [
                        "class Vdemo___024root final {",
                        "  public:",
                        "    struct {",
                        "      VlUnpacked<VlWide<4>/*108:0*/, 4> demo__DOT__host_pending_req_q;",
                        "    };",
                        "};",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (mdir / "Vdemo___024root__0.ll").write_text(
                "\n".join(
                    [
                        "define dso_local void @demo_func(ptr %0, i64 %idx) {",
                        "  %1 = getelementptr inbounds %class.Vdemo___024root, ptr %0, i64 0, i32 0, i32 0",
                        "  %2 = getelementptr inbounds [4 x [4 x i32]], ptr %1, i64 0, i64 %idx",
                        "  %3 = getelementptr inbounds [4 x i32], ptr %2, i64 0, i64 3",
                        "  store i32 9, ptr %3, align 4",
                        "  ret void",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.trace_function_stores(
                mdir,
                ["demo_func"],
                field_names=["demo__DOT__host_pending_req_q"],
            )
            store = payload["functions"]["demo_func"]["stores"][0]

            self.assertTrue(store["dynamic_index"])
            self.assertIn("<dynamic:%idx>", store["element_path"])

    def test_trace_function_stores_maps_struct_anon_geps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            (mdir / "Vdemo___024root.h").write_text(
                "\n".join(
                    [
                        "class Vdemo___024root final {",
                        "  public:",
                        "    struct {",
                        "      CData/*0:0*/ demo__DOT__req_under_rst_seen_q;",
                        "      CData/*0:0*/ demo__DOT__device_a_ready_q;",
                        "    };",
                        "};",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (mdir / "Vdemo___024root__0.ll").write_text(
                "\n".join(
                    [
                        "%struct.anon = type { i8, i8 }",
                        "define dso_local void @demo_func(ptr %0) {",
                        "  %1 = getelementptr inbounds %struct.anon, ptr %0, i64 0, i32 0",
                        "  store i8 1, ptr %1, align 1",
                        "  %2 = getelementptr inbounds %struct.anon, ptr %0, i64 0, i32 1",
                        "  store i8 0, ptr %2, align 1",
                        "  ret void",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.trace_function_stores(
                mdir,
                ["demo_func"],
                field_names=["demo__DOT__req_under_rst_seen_q", "demo__DOT__device_a_ready_q"],
            )
            fields = payload["functions"]["demo_func"]["field_summary"]

            self.assertEqual(fields["demo__DOT__req_under_rst_seen_q"]["store_count"], 1)
            self.assertEqual(fields["demo__DOT__device_a_ready_q"]["store_count"], 1)

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir) / "mdir"
            mdir.mkdir()
            (mdir / "Vdemo___024root.h").write_text(
                "\n".join(
                    [
                        "class Vdemo___024root final {",
                        "  public:",
                        "    struct {",
                        "      VL_OUT(toggle_bitmap_word2_o,31,0);",
                        "    };",
                        "};",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (mdir / "Vdemo___024root__0.ll").write_text(
                "\n".join(
                    [
                        "define dso_local void @demo_func(ptr %0) {",
                        "  %1 = getelementptr inbounds %class.Vdemo___024root, ptr %0, i64 0, i32 0, i32 0",
                        "  store i32 1, ptr %1, align 4",
                        "  ret void",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            json_out = Path(tmpdir) / "trace.json"
            argv = [
                "trace_vl_ir_stores.py",
                str(mdir),
                "demo_func",
                "--json-out",
                str(json_out),
            ]

            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["functions"]["demo_func"]["store_count"], 1)


if __name__ == "__main__":
    unittest.main()
