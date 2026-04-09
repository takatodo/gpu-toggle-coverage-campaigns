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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "compare_vl_hybrid_modes.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class CompareVlHybridModesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("compare_vl_hybrid_modes_test", MODULE_PATH)

    def test_compare_state_dumps_reports_first_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            single = root / "single.bin"
            split = root / "split.bin"
            single.write_bytes(bytes([0x00, 0x11, 0x22, 0x33]))
            split.write_bytes(bytes([0x00, 0x10, 0x22, 0x33]))

            summary = self.module.compare_state_dumps(single, split, storage_size=2)

            self.assertFalse(summary["match"])
            self.assertEqual(summary["mismatch_count"], 1)
            self.assertEqual(summary["first_mismatch"]["global_offset"], 1)
            self.assertEqual(summary["first_mismatch"]["state_index"], 0)
            self.assertEqual(summary["first_mismatch"]["state_offset"], 1)
            self.assertEqual(summary["first_mismatch"]["single_byte"], 0x11)
            self.assertEqual(summary["first_mismatch"]["split_byte"], 0x10)

    def test_compare_state_dumps_annotates_layout_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            single = root / "single.bin"
            split = root / "split.bin"
            single.write_bytes(bytes([0x00, 0x00, 0x22, 0x33]))
            split.write_bytes(bytes([0x00, 0x10, 0x22, 0x30]))

            summary = self.module.compare_state_dumps(
                single,
                split,
                storage_size=4,
                layout=[
                    {"name": "bootstrapped_q", "offset": 1, "size": 1},
                    {"name": "packed_word", "offset": 3, "size": 1},
                ],
            )

            self.assertEqual(summary["first_mismatch"]["field_name"], "bootstrapped_q")
            self.assertEqual(summary["first_mismatch"]["field_offset"], 1)
            self.assertEqual(summary["first_mismatch"]["field_byte_offset"], 0)
            self.assertEqual(summary["mismatch_field_count"], 2)
            self.assertEqual(summary["mismatch_fields"][0]["field_role"], "other")
            self.assertEqual(summary["mismatch_fields"][0]["field_name"], "bootstrapped_q")
            self.assertEqual(summary["mismatch_fields"][1]["field_name"], "packed_word")
            self.assertEqual(summary["acceptance_candidates"]["match_excluding_verilator_internal"], False)

    def test_extract_root_member_names_parses_verilator_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root_h = Path(tmpdir) / "Vdemo___024root.h"
            root_h.write_text(
                "\n".join(
                    [
                        "class Vdemo___024root final {",
                        "  public:",
                        "    struct {",
                        "        VL_IN8(cfg_valid_i,0,0);",
                        "        CData/*0:0*/ demo__DOT__flag_q;",
                        "    };",
                        "    VlDelayScheduler __VdlySched;",
                        "    Vdemo__Syms* vlSymsp;",
                        "    const char* vlNamep;",
                        "    void __Vconfigure(bool first);",
                        "};",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            names = self.module.extract_root_member_names(root_h)

            self.assertEqual(
                names,
                ["cfg_valid_i", "demo__DOT__flag_q", "__VdlySched", "vlSymsp", "vlNamep"],
            )

    def test_compare_state_dumps_reports_internal_only_prefix_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            single = root / "single.bin"
            split = root / "split.bin"
            single.write_bytes(bytes([0x01, 0x00]))
            split.write_bytes(bytes([0x00, 0x00]))

            summary = self.module.compare_state_dumps(
                single,
                split,
                storage_size=2,
                layout=[
                    {"name": "__VicoPhaseResult", "offset": 0, "size": 1},
                    {"name": "demo__DOT__flag_q", "offset": 1, "size": 1},
                ],
            )

            self.assertEqual(summary["mismatch_role_summary"]["verilator_internal"]["mismatch_bytes"], 1)
            self.assertTrue(summary["acceptance_candidates"]["match_excluding_verilator_internal"])
            self.assertIsNone(summary.get("first_non_internal_mismatch"))
            self.assertIsNone(summary.get("first_design_state_mismatch"))

    def test_build_acceptance_policies_distinguishes_strict_and_internal_ignored(self) -> None:
        summary = {
            "match": False,
            "acceptance_candidates": {
                "strict_match": False,
                "match_excluding_verilator_internal": True,
                "verilator_internal_mismatch_bytes": 4,
                "design_state_mismatch_bytes": 0,
                "top_level_io_mismatch_bytes": 0,
                "other_mismatch_bytes": 0,
            },
        }

        policies = self.module.build_acceptance_policies(summary)
        selected = self.module.select_acceptance_policy(
            {"acceptance_policies": policies},
            self.module.ACCEPTANCE_POLICY_IGNORE_INTERNAL,
        )

        self.assertFalse(policies[self.module.ACCEPTANCE_POLICY_STRICT]["passed"])
        self.assertTrue(policies[self.module.ACCEPTANCE_POLICY_IGNORE_INTERNAL]["passed"])
        self.assertEqual(selected["name"], self.module.ACCEPTANCE_POLICY_IGNORE_INTERNAL)
        self.assertTrue(selected["passed"])

    def test_build_phase_delta_summary_keeps_role_and_first_mismatch_annotations(self) -> None:
        summary = {
            "mismatch_count": 3,
            "mismatch_field_count": 2,
            "mismatch_role_summary": {
                "design_state": {"field_count": 1, "mismatch_bytes": 2},
                "top_level_io": {"field_count": 1, "mismatch_bytes": 1},
            },
            "acceptance_candidates": {
                "strict_match": False,
                "match_excluding_verilator_internal": False,
                "verilator_internal_mismatch_bytes": 0,
                "design_state_mismatch_bytes": 2,
                "top_level_io_mismatch_bytes": 1,
                "other_mismatch_bytes": 0,
            },
            "mismatch_fields": [
                {"field_name": "demo__DOT__flag_q", "field_role": "design_state"},
                {"field_name": "ready_o", "field_role": "top_level_io"},
            ],
            "first_mismatch": {"field_name": "demo__DOT__flag_q", "global_offset": 4},
            "first_non_internal_mismatch": {
                "field_name": "demo__DOT__flag_q",
                "field_role": "design_state",
            },
            "first_design_state_mismatch": {
                "field_name": "demo__DOT__flag_q",
                "field_role": "design_state",
            },
        }

        delta = self.module.build_phase_delta_summary(summary)

        self.assertEqual(delta["mismatch_count"], 3)
        self.assertEqual(delta["mismatch_field_count"], 2)
        self.assertEqual(delta["mismatch_role_summary"]["design_state"]["mismatch_bytes"], 2)
        self.assertEqual(delta["mismatch_fields"][0]["field_name"], "demo__DOT__flag_q")
        self.assertEqual(delta["first_non_internal_mismatch"]["field_role"], "design_state")
        self.assertEqual(delta["first_design_state_mismatch"]["field_name"], "demo__DOT__flag_q")

    def test_run_hybrid_forwards_kernel_override(self) -> None:
        calls: list[list[str]] = []

        def _fake_run(cmd: list[str], check: bool) -> None:
            calls.append(list(cmd))

        with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
            self.module.run_hybrid(
                mdir=None,
                cubin=Path("/tmp/fake.cubin"),
                storage_size=64,
                nstates=2,
                steps=3,
                block_size=32,
                dump_state=Path("/tmp/state.bin"),
                patches=["4:0xff"],
                kernels=["k0", "k1"],
            )

        self.assertEqual(
            calls[0],
            [
                sys.executable,
                str(self.module.RUN_VL_HYBRID),
                "--cubin",
                "/tmp/fake.cubin",
                "--storage-size",
                "64",
                "--nstates",
                "2",
                "--steps",
                "3",
                "--block-size",
                "32",
                "--dump-state",
                "/tmp/state.bin",
                "--kernels",
                "k0,k1",
                "--patch",
                "4:0xff",
            ],
        )

    def test_main_builds_single_then_split_and_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "summary.json"
            calls: list[tuple[str, object]] = []

            def _fake_build_vl_gpu(
                mdir_path: Path,
                *,
                sm: str,
                out_cubin: Path,
                force: bool,
                clang_opt: str,
                kernel_split_phases: bool,
            ):
                calls.append(("build", kernel_split_phases, out_cubin.name))
                out_cubin.write_bytes(b"cubin")
                if kernel_split_phases:
                    (mdir_path / "vl_batch_gpu.meta.json").write_text(
                        json.dumps(
                            {
                                "launch_sequence": [
                                    "vl_ico_batch_gpu",
                                    "vl_nba_comb_batch_gpu",
                                    "vl_nba_sequent_batch_gpu",
                                ]
                            }
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                return out_cubin, 2112

            def _fake_run_hybrid(
                *,
                mdir: Path | None,
                cubin: Path | None,
                storage_size: int,
                nstates: int,
                steps: int,
                block_size: int,
                dump_state: Path,
                patches: list[str],
                kernels: list[str] | None = None,
            ) -> None:
                calls.append(
                    ("run", mdir is not None, cubin.name if cubin else None, list(patches), list(kernels or []))
                )
                payload = bytes([1, 2, 3, 4])
                dump_state.write_bytes(payload)

            argv = [
                "compare_vl_hybrid_modes.py",
                str(mdir),
                "--nstates",
                "4",
                "--steps",
                "2",
                "--patch",
                "7:0xaa",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module, "build_vl_gpu", side_effect=_fake_build_vl_gpu):
                with mock.patch.object(self.module, "run_hybrid", side_effect=_fake_run_hybrid):
                    with mock.patch.object(
                        self.module,
                        "probe_root_layout",
                        return_value=[{"name": "flag", "offset": 0, "size": 4}],
                    ):
                        with mock.patch.object(sys, "argv", argv):
                            rc = self.module.main()

            self.assertEqual(rc, 0)
            self.assertEqual(
                calls,
                [
                    ("build", False, "vl_batch_gpu_single.cubin"),
                    ("run", False, "vl_batch_gpu_single.cubin", ["7:0xaa"], []),
                    ("build", True, "vl_batch_gpu_split.cubin"),
                    ("run", True, None, ["7:0xaa"], []),
                    ("run", False, "vl_batch_gpu_split.cubin", ["7:0xaa"], ["vl_ico_batch_gpu"]),
                    ("run", False, "vl_batch_gpu_split.cubin", ["7:0xaa"], ["vl_ico_batch_gpu", "vl_nba_comb_batch_gpu"]),
                    ("run", False, "vl_batch_gpu_split.cubin", ["7:0xaa"], ["vl_ico_batch_gpu", "vl_nba_comb_batch_gpu", "vl_nba_sequent_batch_gpu"]),
                ],
            )
            self.assertTrue(json_out.is_file())
            summary = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertTrue(summary["match"])
            self.assertEqual(summary["storage_size"], 2112)
            self.assertEqual(summary["nstates"], 4)
            self.assertEqual(summary["steps"], 2)
            self.assertEqual(len(summary["phase_debug"]), 3)
            self.assertIsNone(summary["phase_localization"]["first_divergent_prefix_index"])
            self.assertIsNone(summary["phase_localization"]["first_non_internal_prefix_index"])
            self.assertIsNone(summary["phase_localization"]["first_design_state_prefix_index"])
            self.assertIsNone(summary["phase_localization"]["first_delta_prefix_index"])
            self.assertIsNone(summary["phase_localization"]["first_non_internal_delta_prefix_index"])
            self.assertIsNone(summary["phase_localization"]["first_design_state_delta_prefix_index"])
            self.assertEqual(summary["phase_debug"][1]["delta_from_previous_prefix"]["mismatch_count"], 0)
            self.assertEqual(summary["selected_acceptance_policy"]["name"], "strict_final_state")
            self.assertTrue(summary["selected_acceptance_policy"]["passed"])
            self.assertEqual(summary["root_layout_member_count"], 1)
            self.assertEqual(summary["schema_version"], 2)

    def test_main_can_pass_with_ignore_internal_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            def _fake_build_vl_gpu(
                mdir_path: Path,
                *,
                sm: str,
                out_cubin: Path,
                force: bool,
                clang_opt: str,
                kernel_split_phases: bool,
            ):
                out_cubin.write_bytes(b"cubin")
                if kernel_split_phases:
                    (mdir_path / "vl_batch_gpu.meta.json").write_text(
                        json.dumps({"launch_sequence": ["vl_ico_batch_gpu"]}) + "\n",
                        encoding="utf-8",
                    )
                return out_cubin, 2

            run_count = {"value": 0}

            def _fake_run_hybrid(
                *,
                mdir: Path | None,
                cubin: Path | None,
                storage_size: int,
                nstates: int,
                steps: int,
                block_size: int,
                dump_state: Path,
                patches: list[str],
                kernels: list[str] | None = None,
            ) -> None:
                if run_count["value"] == 0:
                    dump_state.write_bytes(bytes([1, 0]))
                else:
                    dump_state.write_bytes(bytes([0, 0]))
                run_count["value"] += 1

            argv = [
                "compare_vl_hybrid_modes.py",
                str(mdir),
                "--acceptance-policy",
                "ignore_verilator_internal_final_state",
            ]
            with mock.patch.object(self.module, "build_vl_gpu", side_effect=_fake_build_vl_gpu):
                with mock.patch.object(self.module, "run_hybrid", side_effect=_fake_run_hybrid):
                    with mock.patch.object(
                        self.module,
                        "probe_root_layout",
                        return_value=[{"name": "__VicoPhaseResult", "offset": 0, "size": 1}],
                    ):
                        with mock.patch.object(sys, "argv", argv):
                            rc = self.module.main()

            self.assertEqual(rc, 0)

    def test_main_can_pass_with_phase_b_endpoint_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            def _fake_build_vl_gpu(
                mdir_path: Path,
                *,
                sm: str,
                out_cubin: Path,
                force: bool,
                clang_opt: str,
                kernel_split_phases: bool,
            ):
                out_cubin.write_bytes(b"cubin")
                if kernel_split_phases:
                    (mdir_path / "vl_batch_gpu.meta.json").write_text(
                        json.dumps({"launch_sequence": ["vl_ico_batch_gpu"]}) + "\n",
                        encoding="utf-8",
                    )
                return out_cubin, 16

            run_count = {"value": 0}

            def _fake_run_hybrid(
                *,
                mdir: Path | None,
                cubin: Path | None,
                storage_size: int,
                nstates: int,
                steps: int,
                block_size: int,
                dump_state: Path,
                patches: list[str],
                kernels: list[str] | None = None,
            ) -> None:
                if run_count["value"] == 0:
                    dump_state.write_bytes(bytes([1, 0, 0, 0, 2, 0, 0, 0, 3, 0, 0, 0, 4]) + b"\x00" * 3)
                else:
                    dump_state.write_bytes(bytes(16))
                run_count["value"] += 1

            argv = [
                "compare_vl_hybrid_modes.py",
                str(mdir),
                "--acceptance-policy",
                "phase_b_endpoint",
            ]
            with mock.patch.object(self.module, "build_vl_gpu", side_effect=_fake_build_vl_gpu):
                with mock.patch.object(self.module, "run_hybrid", side_effect=_fake_run_hybrid):
                    with mock.patch.object(
                        self.module,
                        "probe_root_layout",
                        return_value=[
                            {"name": "__VicoPhaseResult", "offset": 0, "size": 1},
                            {"name": "__VactIterCount", "offset": 4, "size": 4},
                            {"name": "__VinactIterCount", "offset": 8, "size": 4},
                            {"name": "__VicoTriggered", "offset": 12, "size": 1},
                        ],
                    ):
                        with mock.patch.object(sys, "argv", argv):
                            rc = self.module.main()

            self.assertEqual(rc, 0)

    def test_phase_b_endpoint_rejects_unexpected_internal_field(self) -> None:
        summary = {
            "match": False,
            "mismatch_fields": [
                {"field_name": "__VicoPhaseResult", "field_role": "verilator_internal"},
                {"field_name": "__VnbaTriggered", "field_role": "verilator_internal"},
            ],
            "acceptance_candidates": {
                "strict_match": False,
                "match_excluding_verilator_internal": True,
            },
        }
        policies = self.module.build_acceptance_policies(summary)
        self.assertTrue(policies["ignore_verilator_internal_final_state"]["passed"])
        self.assertFalse(policies["phase_b_endpoint"]["passed"])

    def test_main_records_first_non_internal_delta_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "summary.json"

            def _fake_build_vl_gpu(
                mdir_path: Path,
                *,
                sm: str,
                out_cubin: Path,
                force: bool,
                clang_opt: str,
                kernel_split_phases: bool,
            ):
                out_cubin.write_bytes(b"cubin")
                if kernel_split_phases:
                    (mdir_path / "vl_batch_gpu.meta.json").write_text(
                        json.dumps(
                            {
                                "launch_sequence": [
                                    "vl_ico_batch_gpu",
                                    "vl_nba_comb_batch_gpu",
                                    "vl_nba_sequent_batch_gpu",
                                ]
                            }
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                return out_cubin, 4

            def _fake_run_hybrid(
                *,
                mdir: Path | None,
                cubin: Path | None,
                storage_size: int,
                nstates: int,
                steps: int,
                block_size: int,
                dump_state: Path,
                patches: list[str],
                kernels: list[str] | None = None,
            ) -> None:
                dump_state.write_bytes(bytes([0, 0, 0, 0]))

            compare_results = [
                {
                    "match": False,
                    "mismatch_count": 2,
                    "mismatch_fields": [
                        {"field_name": "__VicoPhaseResult", "field_role": "verilator_internal"},
                        {"field_name": "demo__DOT__flag_q", "field_role": "design_state"},
                    ],
                    "mismatch_role_summary": {
                        "verilator_internal": {"field_count": 1, "mismatch_bytes": 1},
                        "design_state": {"field_count": 1, "mismatch_bytes": 1},
                    },
                    "acceptance_candidates": {
                        "strict_match": False,
                        "match_excluding_verilator_internal": False,
                        "verilator_internal_mismatch_bytes": 1,
                        "design_state_mismatch_bytes": 1,
                        "top_level_io_mismatch_bytes": 0,
                        "other_mismatch_bytes": 0,
                    },
                    "first_non_internal_mismatch": {
                        "field_name": "demo__DOT__flag_q",
                        "field_role": "design_state",
                    },
                    "first_design_state_mismatch": {
                        "field_name": "demo__DOT__flag_q",
                        "field_role": "design_state",
                    },
                },
                {
                    "match": False,
                    "mismatch_count": 1,
                    "mismatch_fields": [
                        {"field_name": "__VicoPhaseResult", "field_role": "verilator_internal"}
                    ],
                    "mismatch_role_summary": {
                        "verilator_internal": {"field_count": 1, "mismatch_bytes": 1}
                    },
                    "acceptance_candidates": {
                        "strict_match": False,
                        "match_excluding_verilator_internal": True,
                        "verilator_internal_mismatch_bytes": 1,
                        "design_state_mismatch_bytes": 0,
                        "top_level_io_mismatch_bytes": 0,
                        "other_mismatch_bytes": 0,
                    },
                },
                {
                    "match": False,
                    "mismatch_count": 2,
                    "mismatch_fields": [
                        {"field_name": "__VicoPhaseResult", "field_role": "verilator_internal"},
                        {"field_name": "demo__DOT__flag_q", "field_role": "design_state"},
                    ],
                    "mismatch_role_summary": {
                        "verilator_internal": {"field_count": 1, "mismatch_bytes": 1},
                        "design_state": {"field_count": 1, "mismatch_bytes": 1},
                    },
                    "acceptance_candidates": {
                        "strict_match": False,
                        "match_excluding_verilator_internal": False,
                        "verilator_internal_mismatch_bytes": 1,
                        "design_state_mismatch_bytes": 1,
                        "top_level_io_mismatch_bytes": 0,
                        "other_mismatch_bytes": 0,
                    },
                    "first_non_internal_mismatch": {
                        "field_name": "demo__DOT__flag_q",
                        "field_role": "design_state",
                    },
                    "first_design_state_mismatch": {
                        "field_name": "demo__DOT__flag_q",
                        "field_role": "design_state",
                    },
                },
                {
                    "match": False,
                    "mismatch_count": 1,
                    "mismatch_field_count": 1,
                    "mismatch_fields": [
                        {"field_name": "demo__DOT__flag_q", "field_role": "design_state"}
                    ],
                    "mismatch_role_summary": {
                        "design_state": {"field_count": 1, "mismatch_bytes": 1}
                    },
                    "acceptance_candidates": {
                        "strict_match": False,
                        "match_excluding_verilator_internal": False,
                        "verilator_internal_mismatch_bytes": 0,
                        "design_state_mismatch_bytes": 1,
                        "top_level_io_mismatch_bytes": 0,
                        "other_mismatch_bytes": 0,
                    },
                    "first_non_internal_mismatch": {
                        "field_name": "demo__DOT__flag_q",
                        "field_role": "design_state",
                    },
                    "first_design_state_mismatch": {
                        "field_name": "demo__DOT__flag_q",
                        "field_role": "design_state",
                    },
                },
                {
                    "match": False,
                    "mismatch_count": 2,
                    "mismatch_fields": [
                        {"field_name": "__VicoPhaseResult", "field_role": "verilator_internal"},
                        {"field_name": "demo__DOT__flag_q", "field_role": "design_state"},
                    ],
                    "mismatch_role_summary": {
                        "verilator_internal": {"field_count": 1, "mismatch_bytes": 1},
                        "design_state": {"field_count": 1, "mismatch_bytes": 1},
                    },
                    "acceptance_candidates": {
                        "strict_match": False,
                        "match_excluding_verilator_internal": False,
                        "verilator_internal_mismatch_bytes": 1,
                        "design_state_mismatch_bytes": 1,
                        "top_level_io_mismatch_bytes": 0,
                        "other_mismatch_bytes": 0,
                    },
                    "first_non_internal_mismatch": {
                        "field_name": "demo__DOT__flag_q",
                        "field_role": "design_state",
                    },
                    "first_design_state_mismatch": {
                        "field_name": "demo__DOT__flag_q",
                        "field_role": "design_state",
                    },
                },
                {
                    "match": True,
                    "mismatch_count": 0,
                    "mismatch_fields": [],
                    "mismatch_role_summary": {},
                    "acceptance_candidates": {
                        "strict_match": True,
                        "match_excluding_verilator_internal": True,
                        "verilator_internal_mismatch_bytes": 0,
                        "design_state_mismatch_bytes": 0,
                        "top_level_io_mismatch_bytes": 0,
                        "other_mismatch_bytes": 0,
                    },
                },
            ]

            argv = ["compare_vl_hybrid_modes.py", str(mdir), "--json-out", str(json_out)]
            with mock.patch.object(self.module, "build_vl_gpu", side_effect=_fake_build_vl_gpu):
                with mock.patch.object(self.module, "run_hybrid", side_effect=_fake_run_hybrid):
                    with mock.patch.object(
                        self.module,
                        "probe_root_layout",
                        return_value=[{"name": "flag", "offset": 0, "size": 4}],
                    ):
                        with mock.patch.object(
                            self.module,
                            "compare_state_dumps",
                            side_effect=compare_results,
                        ):
                            with mock.patch.object(sys, "argv", argv):
                                rc = self.module.main()

            self.assertEqual(rc, 2)
            summary = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(summary["phase_localization"]["first_non_internal_prefix_index"], 2)
            self.assertEqual(summary["phase_localization"]["first_design_state_prefix_index"], 2)
            self.assertEqual(summary["phase_localization"]["first_delta_prefix_index"], 2)
            self.assertEqual(summary["phase_localization"]["first_non_internal_delta_prefix_index"], 2)
            self.assertEqual(summary["phase_localization"]["first_design_state_delta_prefix_index"], 2)
            self.assertEqual(
                summary["phase_localization"]["first_non_internal_delta_mismatch"]["field_name"],
                "demo__DOT__flag_q",
            )
            self.assertEqual(
                summary["phase_debug"][1]["delta_from_previous_prefix"]["mismatch_fields"][0]["field_name"],
                "demo__DOT__flag_q",
            )
            self.assertEqual(summary["phase_debug"][2]["delta_from_previous_prefix"]["mismatch_count"], 0)


if __name__ == "__main__":
    unittest.main()
