#!/usr/bin/env python3
"""Standalone sim-accel CUDA kernel fuser.

This tool lives outside Verilator's main `src/` tree on purpose.
It reads generated `full_comb/full_seq/link.cu` sources, builds a small
mid-level model of the kernels, emits a fused `full_all.cu`, and patches the
host launch helpers to use the fused kernel.

The internal IR here is intentionally small and Python-native. It is meant to
be the staging point before experimenting with an LLVM/NVVM backend.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


KERNEL_DECL_TMPL = """extern "C" __global__ void {name}(const uint64_t* state_in,
                                                   uint64_t* state_out,
                                                   uint32_t nstates) {{
    const uint32_t tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= nstates) return;
    {{
{body}
    }}
}}
"""


@dataclass(frozen=True)
class LoadOp:
    target: str
    source_buffer: str
    index_expr: str
    width_bits: int
    comment: str


@dataclass(frozen=True)
class TempInitOp:
    target: str
    value_expr: str
    comment: str


@dataclass(frozen=True)
class AssignOp:
    target: str
    expr: str
    comment: str


@dataclass(frozen=True)
class StoreOp:
    index_expr: str
    value_expr: str
    width_bits: int


@dataclass(frozen=True)
class ExprSpec:
    symbol: str
    expr: str
    args: list[str]


DeclarationOp = LoadOp | TempInitOp


@dataclass(frozen=True)
class KernelPhase:
    declarations: list[DeclarationOp]
    assignments: list[AssignOp]
    stores: list[StoreOp]


@dataclass(frozen=True)
class KernelSource:
    prefix: str
    phase: KernelPhase


def _find_enclosed_block(text: str, brace_start: int) -> int:
    depth = 0
    for idx in range(brace_start, len(text)):
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return idx + 1
    raise ValueError("Could not find matching brace")


def _extract_function(text: str, marker: str) -> tuple[int, int]:
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"Could not find function marker: {marker}")
    brace_start = text.find("{", start)
    if brace_start < 0:
        raise ValueError(f"Could not find function body start: {marker}")
    end = _find_enclosed_block(text, brace_start)
    return start, end


def _extract_kernel_phase_lines(text: str, kernel_name: str) -> tuple[str, list[str]]:
    marker = f'extern "C" __global__ void {kernel_name}'
    start, end = _extract_function(text, marker)
    prefix = text[:start]
    func = text[start:end]
    needle = "    if (tid >= nstates) return;\n"
    after_if = func.find(needle)
    if after_if < 0:
        raise ValueError(f"Could not find thread guard in {kernel_name}")
    block_start = func.find("{", after_if + len(needle))
    if block_start < 0:
        raise ValueError(f"Could not find inner block in {kernel_name}")
    block_end = _find_enclosed_block(func, block_start)
    block = func[block_start + 1:block_end - 1]
    lines = [line for line in block.splitlines() if line.strip()]
    return prefix, lines


def _classify_phase(lines: list[str]) -> KernelPhase:
    declarations: list[DeclarationOp] = []
    assignments: list[AssignOp] = []
    stores: list[StoreOp] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("uint64_t "):
            declarations.append(_parse_declaration(stripped))
            continue
        if stripped.startswith("state_out["):
            stores.append(_parse_store(stripped))
            continue
        assignments.append(_parse_assignment(stripped))
    return KernelPhase(declarations=declarations, assignments=assignments, stores=stores)


def load_kernel(path: Path, kernel_name: str) -> KernelSource:
    text = path.read_text(encoding="utf-8")
    prefix, phase_lines = _extract_kernel_phase_lines(text, kernel_name)
    return KernelSource(prefix=prefix, phase=_classify_phase(phase_lines))


def _parse_declaration(line: str) -> DeclarationOp:
    load_match = re.match(
        r"uint64_t\s+([a-z]_[0-9]+)\s*=\s*sim_accel_apply_mask_u64\((state_in|state_out)\[(.+)\],\s*([0-9]+)u\);\s*//\s*(.+)",
        line,
    )
    if load_match:
        return LoadOp(
            target=load_match.group(1),
            source_buffer=load_match.group(2),
            index_expr=load_match.group(3),
            width_bits=int(load_match.group(4)),
            comment=load_match.group(5),
        )
    init_match = re.match(r"uint64_t\s+([a-z]_[0-9]+)\s*=\s*(.+);\s*//\s*(.+)", line)
    if init_match:
        return TempInitOp(
            target=init_match.group(1),
            value_expr=init_match.group(2),
            comment=init_match.group(3),
        )
    raise ValueError(f"Could not parse declaration: {line}")


def _parse_assignment(line: str) -> AssignOp:
    match = re.match(r"([a-z]_[0-9]+)\s*=\s*(.+);\s*//\s*(.+)", line)
    if not match:
        raise ValueError(f"Could not parse assignment: {line}")
    return AssignOp(target=match.group(1), expr=match.group(2), comment=match.group(3))


def _parse_store(line: str) -> StoreOp:
    match = re.match(
        r"state_out\[(.+)\]\s*=\s*sim_accel_apply_mask_u64\((.+),\s*([0-9]+)u\);", line
    )
    if not match:
        raise ValueError(f"Could not parse store: {line}")
    return StoreOp(index_expr=match.group(1), value_expr=match.group(2), width_bits=int(match.group(3)))


def _decl_target(op: DeclarationOp) -> str:
    return op.target


def _render_declaration(op: DeclarationOp) -> str:
    if isinstance(op, LoadOp):
        return (
            f"    uint64_t {op.target} = sim_accel_apply_mask_u64("
            f"{op.source_buffer}[{op.index_expr}], {op.width_bits}u);  // {op.comment}"
        )
    return f"    uint64_t {op.target} = {op.value_expr};  // {op.comment}"


def _render_assignment(op: AssignOp) -> str:
    return f"    {op.target} = {op.expr};  // {op.comment}"


def _render_store(op: StoreOp) -> str:
    return (
        f"    state_out[{op.index_expr}] = "
        f"sim_accel_apply_mask_u64({op.value_expr}, {op.width_bits}u);"
    )


def _render_phase_cuda(phase: KernelPhase) -> str:
    lines: list[str] = []
    lines.extend(_render_declaration(op) + "\n" for op in phase.declarations)
    lines.append("\n")
    lines.extend(_render_assignment(op) + "\n" for op in phase.assignments)
    lines.append("\n")
    lines.extend(_render_store(op) + "\n" for op in phase.stores)
    return "".join(lines)


def _render_phase_ssa(phase: KernelPhase, kernel_name: str) -> str:
    lines = [f"kernel {kernel_name}(state_in, state_out, nstates, tid)\n"]
    for op in phase.declarations:
        if isinstance(op, LoadOp):
            lines.append(
                f"  %{op.target} = load {op.source_buffer}[{op.index_expr}] width={op.width_bits} ; {op.comment}\n"
            )
        else:
            lines.append(f"  %{op.target} = init {op.value_expr} ; {op.comment}\n")
    for op in phase.assignments:
        lines.append(f"  %{op.target} = expr {op.expr} ; {op.comment}\n")
    for op in phase.stores:
        lines.append(
            f"  store state_out[{op.index_expr}] <- {op.value_expr} width={op.width_bits}\n"
        )
    return "".join(lines)


def merge_kernels(comb: KernelSource, seq: KernelSource) -> KernelSource:
    declared = {_decl_target(op) for op in comb.phase.declarations}
    merged_decls = list(comb.phase.declarations)

    for decl in seq.phase.declarations:
        name = _decl_target(decl)
        if name in declared:
            continue
        if isinstance(decl, LoadOp) and decl.source_buffer == "state_out" and decl.target.startswith("v_"):
            decl = LoadOp(
                target=decl.target,
                source_buffer="state_in",
                index_expr=decl.index_expr,
                width_bits=decl.width_bits,
                comment=decl.comment,
            )
        merged_decls.append(decl)
        declared.add(name)

    return KernelSource(
        prefix=comb.prefix,
        phase=KernelPhase(
            declarations=merged_decls,
            assignments=list(comb.phase.assignments) + list(seq.phase.assignments),
            stores=list(comb.phase.stores) + list(seq.phase.stores),
        ),
    )


def emit_cuda_kernel(source: KernelSource, kernel_name: str) -> str:
    return source.prefix + KERNEL_DECL_TMPL.format(
        name=kernel_name, body=_render_phase_cuda(source.phase)
    )


def emit_ssa_kernel(source: KernelSource, kernel_name: str) -> str:
    return _render_phase_ssa(source.phase, kernel_name)


def _extract_expr_args(expr: str) -> list[str]:
    args: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"\b([vn]_[0-9]+)\b", expr):
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        args.append(name)
    return args


def _make_expr_spec(expr: str) -> ExprSpec:
    digest = hashlib.sha1(expr.encode("utf-8")).hexdigest()[:16]
    return ExprSpec(symbol=f"@simaccel_expr_{digest}", expr=expr, args=_extract_expr_args(expr))


def _strip_outer_parens(expr: str) -> str:
    expr = expr.strip()
    while expr.startswith("(") and expr.endswith(")"):
        depth = 0
        fully_wrapped = True
        for idx, ch in enumerate(expr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and idx != len(expr) - 1:
                    fully_wrapped = False
                    break
        if not fully_wrapped:
            break
        expr = expr[1:-1].strip()
    return expr


def _find_top_level_conditional(expr: str) -> tuple[str, str, str] | None:
    depth = 0
    qmark = None
    nested = 0
    for idx, ch in enumerate(expr):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            if ch == "?":
                if qmark is None:
                    qmark = idx
                else:
                    nested += 1
            elif ch == ":" and qmark is not None:
                if nested == 0:
                    return (
                        expr[:qmark].strip(),
                        expr[qmark + 1:idx].strip(),
                        expr[idx + 1:].strip(),
                    )
                nested -= 1
    return None


def _is_unary_site(expr: str, idx: int) -> bool:
    j = idx - 1
    while j >= 0 and expr[j].isspace():
        j -= 1
    if j < 0:
        return True
    return expr[j] in "(,?:+-*/%&|^!~<>= "


def _find_top_level_binary(expr: str, operators: tuple[str, ...]) -> tuple[int, str] | None:
    depth = 0
    best: tuple[int, str] | None = None
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            for op in sorted(operators, key=len, reverse=True):
                if expr.startswith(op, i):
                    if op in {"+", "-"} and _is_unary_site(expr, i):
                        continue
                    if op in {"<", ">"}:
                        prev_ch = expr[i - 1] if i > 0 else ""
                        next_ch = expr[i + 1] if i + 1 < len(expr) else ""
                        if prev_ch == op or next_ch == op:
                            continue
                    if op in {"&", "|"}:
                        prev_ch = expr[i - 1] if i > 0 else ""
                        next_ch = expr[i + 1] if i + 1 < len(expr) else ""
                        if prev_ch == op or next_ch == op:
                            continue
                    best = (i, op)
                    i += len(op) - 1
                    break
        i += 1
    return best


def _split_call(expr: str) -> tuple[str, list[str]] | None:
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\(", expr)
    if not match:
        return None
    name = match.group(1)
    start = len(name)
    if start >= len(expr) or expr[start] != "(" or not expr.endswith(")"):
        return None
    depth = 0
    args: list[str] = []
    current: list[str] = []
    for idx, ch in enumerate(expr[start + 1:-1], start=start + 1):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    args.append("".join(current).strip())
    return name, args


def _const_i64(expr: str) -> int | None:
    value = expr.strip()
    if value == "true":
        return 1
    if value == "false":
        return 0
    if re.fullmatch(r"0x[0-9a-fA-F]+ull", value):
        return int(value[:-3], 16)
    if re.fullmatch(r"[0-9]+ull", value):
        return int(value[:-3], 10)
    if re.fullmatch(r"[0-9]+u", value):
        return int(value[:-1], 10)
    if re.fullmatch(r"[0-9]+", value):
        return int(value, 10)
    return None


def _const_i32(expr: str) -> int | None:
    value = _const_i64(expr)
    if value is None:
        return None
    if value < 0 or value > 0xFFFFFFFF:
        return None
    return value


def _parse_state_index(index_expr: str) -> tuple[int, str]:
    match = re.fullmatch(r"([0-9]+)U \* nstates \+ tid", index_expr.strip())
    if not match:
        raise ValueError(f"Unsupported state index expression: {index_expr}")
    return int(match.group(1)), "%tid"


def _llvm_i64_const(value_expr: str) -> str:
    value = value_expr.strip()
    if value.endswith("ull"):
        value = value[:-3]
    return str(int(value, 0))


AMDGPU_DATALAYOUT = (
    "e-p:64:64-p1:64:64-p2:32:32-p3:32:32-p4:64:64-p5:32:32-p6:32:32-"
    "p7:160:256:256:32-p8:128:128:128:48-p9:192:256:256:32-i64:64-"
    "v16:16-v24:32-v32:32-v48:64-v96:128-v192:256-v256:256-v512:512-"
    "v1024:1024-v2048:2048-n32:64-S32-A5-G1-ni:7:8:9"
)

ROCM_LLVM_CANDIDATE_DIRS = (
    Path("/opt/rocm/lib/llvm/bin"),
    Path("/opt/rocm-7.2.0/lib/llvm/bin"),
)

CACHE_FORMAT_VERSION = 1
DEFAULT_CACHE_ROOT = Path(
    os.environ.get("SIM_ACCEL_FULL_KERNEL_FUSER_CACHE_DIR", "/tmp/sim_accel_full_kernel_fuser_cache")
)
BASE_ARTIFACT_FILENAMES = (
    "kernel_generated.full_all.cu",
    "kernel_generated.full_all.ssa",
    "kernel_generated.full_all.ll",
    "kernel_generated.full_all.backend.json",
)


def _resolve_rocm_llvm_tool(explicit: str, tool_name: str) -> str:
    if explicit and explicit not in {"clang", "ld.lld"}:
        resolved = shutil.which(explicit) if "/" not in explicit else explicit
        if resolved:
            return resolved
    for base in ROCM_LLVM_CANDIDATE_DIRS:
        candidate = base / tool_name
        if candidate.is_file():
            return str(candidate)
    fallback_name = explicit or tool_name
    resolved = shutil.which(fallback_name) if "/" not in fallback_name else fallback_name
    if resolved:
        return resolved
    raise RuntimeError(f"Could not find {tool_name} executable: {explicit or tool_name}")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _script_cache_salt() -> str:
    return _sha256_file(Path(__file__))


def _compute_base_cache_key(
    *,
    full_comb_path: Path,
    full_seq_path: Path,
    llvm_backend_target: str,
) -> str:
    payload = {
        "cache_format_version": CACHE_FORMAT_VERSION,
        "script_sha256": _script_cache_salt(),
        "llvm_backend_target": llvm_backend_target,
        "full_comb_sha256": _sha256_file(full_comb_path),
        "full_seq_sha256": _sha256_file(full_seq_path),
    }
    return _sha256_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))


def _base_cache_entry_ready(entry_dir: Path) -> bool:
    if not entry_dir.is_dir():
        return False
    return all((entry_dir / name).is_file() for name in BASE_ARTIFACT_FILENAMES)


def _restore_base_artifacts(entry_dir: Path, out_dir: Path) -> None:
    for name in BASE_ARTIFACT_FILENAMES:
        shutil.copy2(entry_dir / name, out_dir / name)


def _populate_base_cache(entry_dir: Path, out_dir: Path, *, metadata: dict[str, object]) -> None:
    if _base_cache_entry_ready(entry_dir):
        return
    entry_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = entry_dir.parent / f"{entry_dir.name}.tmp.{os.getpid()}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        for name in BASE_ARTIFACT_FILENAMES:
            shutil.copy2(out_dir / name, tmp_dir / name)
        (tmp_dir / "manifest.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            tmp_dir.replace(entry_dir)
        except FileExistsError:
            shutil.rmtree(tmp_dir)
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)


def emit_llvm_ir(source: KernelSource, kernel_name: str, *, backend_target: str = "nvptx") -> str:
    if backend_target not in {"nvptx", "rocdl"}:
        raise RuntimeError(f"Unsupported backend_target: {backend_target}")
    phase = source.phase
    body_lines: list[str] = []
    opaque_specs: dict[str, ExprSpec] = {}
    lowered_count = 0
    opaque_count = 0
    current_values: dict[str, str] = {}
    version: dict[str, int] = {}
    state_ptr_ty = "ptr" if backend_target == "nvptx" else "ptr addrspace(1)"

    def new_name(base: str) -> str:
        idx = version.get(base, 0)
        version[base] = idx + 1
        return f"%{base}.{idx}"

    def lower_expr(expr: str) -> tuple[str, bool]:
        expr = _strip_outer_parens(expr)

        if expr in current_values:
            return current_values[expr], True

        const_i64 = _const_i64(expr)
        if const_i64 is not None:
            return str(const_i64), True

        cond_parts = _find_top_level_conditional(expr)
        if cond_parts is not None:
            cond_expr, then_expr, else_expr = cond_parts
            cond_value, cond_ok = lower_expr(cond_expr)
            then_value, then_ok = lower_expr(then_expr)
            else_value, else_ok = lower_expr(else_expr)
            if not cond_ok or not then_ok or not else_ok:
                return lower_opaque(expr)
            pred_name = new_name("select_pred")
            out_name = new_name("select")
            body_lines.append(f"  {pred_name} = icmp ne i64 {cond_value}, 0\n")
            body_lines.append(
                f"  {out_name} = select i1 {pred_name}, i64 {then_value}, i64 {else_value}\n"
            )
            return out_name, True

        for operators, opname, llvm_ty, zext in (
            (("==", "!=", ">=", ">", "<=", "<"), "icmp", "i1", True),
            (("|",), "or", "i64", False),
            (("^",), "xor", "i64", False),
            (("&",), "and", "i64", False),
            (("<<",), "shl", "i64", False),
            ((">>",), "lshr", "i64", False),
            (("+", "-"), "arith", "i64", False),
            (("*",), "mul", "i64", False),
        ):
            split = _find_top_level_binary(expr, operators)
            if split is None:
                continue
            idx, op = split
            lhs = expr[:idx].strip()
            rhs = expr[idx + len(op):].strip()
            lhs_value, lhs_ok = lower_expr(lhs)
            rhs_value, rhs_ok = lower_expr(rhs)
            if not lhs_ok or not rhs_ok:
                return lower_opaque(expr)
            if opname == "icmp":
                pred_map = {
                    "==": "eq",
                    "!=": "ne",
                    ">": "ugt",
                    ">=": "uge",
                    "<": "ult",
                    "<=": "ule",
                }
                cmp_name = new_name("icmp")
                body_lines.append(f"  {cmp_name} = icmp {pred_map[op]} i64 {lhs_value}, {rhs_value}\n")
                zext_name = new_name("icmp_zext")
                body_lines.append(f"  {zext_name} = zext i1 {cmp_name} to i64\n")
                return zext_name, True
            if opname == "arith":
                inst = "add" if op == "+" else "sub"
                out_name = new_name(inst)
                body_lines.append(f"  {out_name} = {inst} i64 {lhs_value}, {rhs_value}\n")
                return out_name, True
            out_name = new_name(opname)
            body_lines.append(f"  {out_name} = {opname} i64 {lhs_value}, {rhs_value}\n")
            return out_name, True

        if expr.startswith("~"):
            inner, ok = lower_expr(expr[1:].strip())
            if not ok:
                return lower_opaque(expr)
            out_name = new_name("not")
            body_lines.append(f"  {out_name} = xor i64 {inner}, -1\n")
            return out_name, True

        if expr.startswith("static_cast<uint64_t>(") and expr.endswith(")"):
            return lower_expr(expr[len("static_cast<uint64_t>("):-1])

        call = _split_call(expr)
        if call is not None:
            func_name, call_args = call
            if func_name == "sim_accel_apply_mask_u64" and len(call_args) == 2:
                value, value_ok = lower_expr(call_args[0])
                width = _const_i32(call_args[1])
                if value_ok and width is not None:
                    out_name = new_name("mask")
                    body_lines.append(f"  {out_name} = call i64 @simaccel_mask(i64 {value}, i32 {width})\n")
                    return out_name, True
            return lower_opaque(expr)

        return lower_opaque(expr)

    def lower_opaque(expr: str) -> tuple[str, bool]:
        spec = opaque_specs.get(expr)
        if spec is None:
            spec = _make_expr_spec(expr)
            opaque_specs[expr] = spec
        args = []
        for arg in spec.args:
            if arg not in current_values:
                raise ValueError(f"Opaque expr references unknown value: {arg} in {expr}")
            args.append(f"i64 {current_values[arg]}")
        out_name = new_name("expr")
        body_lines.append(f"  {out_name} = call i64 {spec.symbol}({', '.join(args)})\n")
        return out_name, False

    for op in phase.declarations:
        if isinstance(op, LoadOp):
            slot, tid_name = _parse_state_index(op.index_expr)
            mul_name = new_name(f"{op.target}_slotmul")
            idx_name = new_name(f"{op.target}_idx")
            ptr_name = new_name(f"{op.target}_ptr")
            raw_name = new_name(f"{op.target}_raw")
            val_name = new_name(op.target)
            body_lines.append(f"  {mul_name} = mul nuw i32 {slot}, %nstates\n")
            body_lines.append(f"  {idx_name} = add nuw i32 {mul_name}, {tid_name}\n")
            body_lines.append(
                f"  {ptr_name} = getelementptr i64, {state_ptr_ty} %{op.source_buffer}, i32 {idx_name}\n"
            )
            body_lines.append(f"  {raw_name} = load i64, {state_ptr_ty} {ptr_name}, align 8\n")
            body_lines.append(
                f"  {val_name} = call i64 @simaccel_mask(i64 {raw_name}, i32 {op.width_bits})"
                f" ; {op.comment}\n"
            )
            current_values[op.target] = val_name
        else:
            val_name = new_name(op.target)
            body_lines.append(
                f"  {val_name} = add i64 0, {_llvm_i64_const(op.value_expr)} ; {op.comment}\n"
            )
            current_values[op.target] = val_name

    if phase.declarations:
        body_lines.append("\n")

    for op in phase.assignments:
        value_name, lowered = lower_expr(op.expr)
        target_name = new_name(op.target)
        if value_name.startswith("%"):
            body_lines.append(f"  {target_name} = add i64 0, {value_name} ; {op.comment}\n")
        else:
            body_lines.append(f"  {target_name} = add i64 0, {value_name} ; {op.comment}\n")
        current_values[op.target] = target_name
        if lowered:
            lowered_count += 1
        else:
            opaque_count += 1

    if phase.assignments:
        body_lines.append("\n")

    for op in phase.stores:
        slot, tid_name = _parse_state_index(op.index_expr)
        mul_name = new_name("store_slotmul")
        idx_name = new_name("store_idx")
        ptr_name = new_name("store_ptr")
        masked_name = new_name("store_masked")
        value_name = current_values[op.value_expr]
        body_lines.append(f"  {mul_name} = mul nuw i32 {slot}, %nstates\n")
        body_lines.append(f"  {idx_name} = add nuw i32 {mul_name}, {tid_name}\n")
        body_lines.append(f"  {ptr_name} = getelementptr i64, {state_ptr_ty} %state_out, i32 {idx_name}\n")
        body_lines.append(
            f"  {masked_name} = call i64 @simaccel_mask(i64 {value_name}, i32 {op.width_bits})\n"
        )
        body_lines.append(f"  store i64 {masked_name}, {state_ptr_ty} {ptr_name}, align 8\n")

    lines: list[str] = []
    lines.append("; ModuleID = 'sim_accel_full_all'\n")
    if backend_target == "nvptx":
        lines.append("target triple = \"nvptx64-nvidia-cuda\"\n")
    else:
        lines.append(f'target datalayout = "{AMDGPU_DATALAYOUT}"\n')
        lines.append('target triple = "amdgcn-amd-amdhsa"\n')
    lines.append(f"; lowered_assignments={lowered_count}\n")
    lines.append(f"; opaque_assignments={opaque_count}\n\n")
    if backend_target == "nvptx":
        lines.append("declare i32 @llvm.nvvm.read.ptx.sreg.tid.x()\n")
        lines.append("declare i32 @llvm.nvvm.read.ptx.sreg.ntid.x()\n")
        lines.append("declare i32 @llvm.nvvm.read.ptx.sreg.ctaid.x()\n\n")
    else:
        lines.append(
            "declare noundef range(i32 0, 1024) i32 @llvm.amdgcn.workitem.id.x()\n"
        )
        lines.append("declare noundef i32 @llvm.amdgcn.workgroup.id.x()\n")
        lines.append("declare noundef align 4 ptr addrspace(4) @llvm.amdgcn.implicitarg.ptr()\n\n")
    lines.append("define internal i64 @simaccel_mask(i64 %value, i32 %width) {\n")
    lines.append("entry:\n")
    lines.append("  %is_full = icmp uge i32 %width, 64\n")
    lines.append("  br i1 %is_full, label %ret_full, label %check_zero\n\n")
    lines.append("check_zero:\n")
    lines.append("  %is_zero = icmp eq i32 %width, 0\n")
    lines.append("  br i1 %is_zero, label %ret_zero, label %mask_bits\n\n")
    lines.append("mask_bits:\n")
    lines.append("  %width64 = zext i32 %width to i64\n")
    lines.append("  %shifted = shl i64 1, %width64\n")
    lines.append("  %mask = add i64 %shifted, -1\n")
    lines.append("  %masked = and i64 %value, %mask\n")
    lines.append("  ret i64 %masked\n\n")
    lines.append("ret_zero:\n")
    lines.append("  ret i64 0\n\n")
    lines.append("ret_full:\n")
    lines.append("  ret i64 %value\n")
    lines.append("}\n")
    for spec in sorted(opaque_specs.values(), key=lambda item: item.symbol):
        args = ", ".join("i64" for _ in spec.args)
        lines.append(f"declare i64 {spec.symbol}({args}) ; expr: {spec.expr}\n")
    lines.append("\n")
    lines.append(
        f"define internal void @{kernel_name}_ssa({state_ptr_ty} %state_in, {state_ptr_ty} %state_out, i32 %nstates, i32 %tid) {{\n"
    )
    lines.append("entry:\n")
    lines.append("  %tid_oob = icmp uge i32 %tid, %nstates\n")
    lines.append("  br i1 %tid_oob, label %exit, label %body\n\n")
    lines.append("body:\n")
    lines.extend(body_lines)
    lines.append("  br label %exit\n\n")
    lines.append("exit:\n")
    lines.append("  ret void\n")
    lines.append("}\n")
    lines.append("\n")
    kernel_cc = "void"
    kernel_attrs = ""
    if backend_target == "rocdl":
        kernel_cc = "amdgpu_kernel void"
        kernel_attrs = " #0"
    lines.append(f"define {kernel_cc} @{kernel_name}({state_ptr_ty} %state_in, {state_ptr_ty} %state_out, i32 %nstates){kernel_attrs} {{\n")
    lines.append("entry:\n")
    if backend_target == "nvptx":
        lines.append("  %tid_x = call i32 @llvm.nvvm.read.ptx.sreg.tid.x()\n")
        lines.append("  %ntid_x = call i32 @llvm.nvvm.read.ptx.sreg.ntid.x()\n")
        lines.append("  %ctaid_x = call i32 @llvm.nvvm.read.ptx.sreg.ctaid.x()\n")
        lines.append("  %block_base = mul i32 %ctaid_x, %ntid_x\n")
    else:
        lines.append("  %ctaid_x = call i32 @llvm.amdgcn.workgroup.id.x()\n")
        lines.append("  %implicitarg = call ptr addrspace(4) @llvm.amdgcn.implicitarg.ptr()\n")
        lines.append("  %ntid_x_ptr = getelementptr inbounds nuw i8, ptr addrspace(4) %implicitarg, i64 12\n")
        lines.append("  %ntid_x_raw = load i16, ptr addrspace(4) %ntid_x_ptr, align 4\n")
        lines.append("  %ntid_x = zext i16 %ntid_x_raw to i32\n")
        lines.append("  %tid_x = call i32 @llvm.amdgcn.workitem.id.x()\n")
        lines.append("  %block_base = mul i32 %ctaid_x, %ntid_x\n")
    lines.append("  %tid = add i32 %block_base, %tid_x\n")
    lines.append(
        f"  call void @{kernel_name}_ssa({state_ptr_ty} %state_in, {state_ptr_ty} %state_out, i32 %nstates, i32 %tid)\n"
    )
    lines.append("  ret void\n")
    lines.append("}\n")
    lines.append("\n")
    if backend_target == "nvptx":
        lines.append("!nvvm.annotations = !{!0}\n")
        lines.append(f"!0 = !{{ptr @{kernel_name}, !\"kernel\", i32 1}}\n")
    else:
        lines.append(
            'attributes #0 = { mustprogress nofree norecurse nosync nounwind willreturn '
            'memory(argmem: readwrite) "amdgpu-flat-work-group-size"="1,1024" '
            '"uniform-work-group-size"="true" }\n'
        )
        lines.append("!llvm.module.flags = !{!0}\n")
        lines.append('!0 = !{i32 1, !"amdhsa_code_object_version", i32 600}\n')
    return "".join(lines)


def emit_ptx(
    llvm_path: Path,
    ptx_path: Path,
    *,
    clang_path: str,
    cuda_arch: str | None,
) -> None:
    llc_bin = shutil.which("llc-18") or shutil.which("llc")
    if llc_bin:
        cmd = [llc_bin, "-march=nvptx64"]
        if cuda_arch:
            cmd.append(f"-mcpu={cuda_arch}")
        cmd.extend(["-o", str(ptx_path), str(llvm_path)])
        subprocess.run(cmd, check=True)
        return
    clang_bin = shutil.which(clang_path) if "/" not in clang_path else clang_path
    if not clang_bin:
        raise RuntimeError(f"Could not find clang executable: {clang_path}")
    cmd = [
        clang_bin,
        "-S",
        "-x",
        "ir",
        "--target=nvptx64-nvidia-cuda",
        "-nocudalib",
        str(llvm_path),
        "-o",
        str(ptx_path),
    ]
    if cuda_arch:
        cmd.insert(-2, f"--cuda-gpu-arch={cuda_arch}")
    subprocess.run(cmd, check=True)


def emit_hsaco(
    llvm_path: Path,
    hsaco_path: Path,
    *,
    clang_path: str,
    ld_lld_path: str,
    gfx_arch: str,
) -> None:
    clang_bin = _resolve_rocm_llvm_tool(clang_path, "clang")
    ld_lld_bin = _resolve_rocm_llvm_tool(ld_lld_path, "ld.lld")
    obj_path = hsaco_path.with_suffix(".o")
    cmd_compile = [
        clang_bin,
        "-x",
        "ir",
        "--target=amdgcn-amd-amdhsa",
        f"-mcpu={gfx_arch}",
        "-nogpulib",
        "-c",
        str(llvm_path),
        "-o",
        str(obj_path),
    ]
    subprocess.run(cmd_compile, check=True)
    cmd_link = [ld_lld_bin, "-shared", str(obj_path), "-o", str(hsaco_path)]
    subprocess.run(cmd_link, check=True)


def _infer_ptx_target_arch(ptx_path: Path) -> str | None:
    text = ptx_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"(?m)^\.target\s+([A-Za-z0-9_]+)\b", text)
    if match is None:
        return None
    arch = match.group(1)
    return arch if arch.startswith("sm_") else None


def validate_ptx(ptx_path: Path, *, ptxas_path: str, cuda_arch: str | None = None) -> Path:
    ptxas_bin = shutil.which(ptxas_path) if "/" not in ptxas_path else ptxas_path
    if not ptxas_bin:
        raise RuntimeError(f"Could not find ptxas executable: {ptxas_path}")
    cubin_path = ptx_path.with_suffix(".cubin")
    target_arch = cuda_arch or _infer_ptx_target_arch(ptx_path)
    cmd = [ptxas_bin]
    if target_arch:
        cmd.append(f"-arch={target_arch}")
    cmd.extend([str(ptx_path), "-o", str(cubin_path)])
    subprocess.run(cmd, check=True)
    return cubin_path


def _insert_full_all_decl(text: str) -> str:
    if "sim_accel_eval_assignw_u32_full_all" in text:
        return text
    anchor_match = None
    for kernel_name in (
        "sim_accel_eval_assignw_u32_full_seq",
        "sim_accel_eval_assignw_u32_full_comb",
    ):
        anchor_re = re.compile(
            rf'extern "C" __global__ void {kernel_name}\('
            r'.*?\);\n',
            flags=re.DOTALL,
        )
        anchor_match = anchor_re.search(text)
        if anchor_match is not None:
            break
    if anchor_match is None:
        raise ValueError("Could not find full_comb/full_seq declaration in link source")
    decl = (
        'extern "C" __global__ void sim_accel_eval_assignw_u32_full_all(const uint64_t* state_in,\n'
        "                                                        uint64_t* state_out,\n"
        "                                                        uint32_t nstates);\n"
    )
    return text[:anchor_match.end()] + decl + text[anchor_match.end():]


def _replace_function(text: str, func_name: str, replacement: str) -> str:
    marker = f'extern "C" __host__ cudaError_t {func_name}('
    start, end = _extract_function(text, marker)
    return text[:start] + replacement + text[end:]


def patch_link_source(text: str, state_var_count: int) -> str:
    text = _insert_full_all_decl(text)
    launch_all_inplace = """extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_all_inplace(uint64_t* state,
                                                        uint32_t nstates,
                                                        uint32_t block_size) {
    const uint32_t block = block_size ? block_size : 256U;
    const uint32_t grid = (nstates + block - 1U) / block;
    sim_accel_eval_assignw_u32_full_all<<<grid, block>>>(state, state, nstates);
    cudaError_t status = cudaGetLastError();
    if (status != cudaSuccess) return status;
    return status;
}"""
    launch_all = f"""extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_all(const uint64_t* state_in,
                                                        uint64_t* state_out,
                                                        uint32_t nstates,
                                                        uint32_t block_size) {{
    if (state_in == state_out) {{
        return sim_accel_eval_assignw_launch_all_inplace(state_out, nstates, block_size);
    }}
    const uint32_t block = block_size ? block_size : 256U;
    const uint32_t grid = (nstates + block - 1U) / block;
    cudaError_t status = cudaMemcpy(state_out, state_in,
                                    {state_var_count}U * static_cast<size_t>(nstates) * sizeof(uint64_t),
                                    cudaMemcpyDeviceToDevice);
    if (status != cudaSuccess) return status;
    sim_accel_eval_assignw_u32_full_all<<<grid, block>>>(state_in, state_out, nstates);
    status = cudaGetLastError();
    if (status != cudaSuccess) return status;
    return status;
}}"""
    text = _replace_function(text, "sim_accel_eval_assignw_launch_all_inplace", launch_all_inplace)
    text = _replace_function(text, "sim_accel_eval_assignw_launch_all", launch_all)
    return text


def _infer_state_var_count(link_text: str) -> int:
    match = re.search(
        r"cudaMemcpy\(state_out, state_in,\s+([0-9]+)U \* static_cast<size_t>\(nstates\) \* sizeof\(uint64_t\)",
        link_text,
        flags=re.MULTILINE,
    )
    if not match:
        raise ValueError("Could not infer state var count from link source")
    return int(match.group(1))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fuse generated sim-accel full_comb/full_seq CUDA kernels into full_all."
    )
    parser.add_argument("--full-comb", type=Path, required=True, help="Input kernel_generated.full_comb.cu")
    parser.add_argument("--full-seq", type=Path, required=True, help="Input kernel_generated.full_seq.cu")
    parser.add_argument("--link", type=Path, required=True, help="Input kernel_generated.link.cu")
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Directory where kernel_generated.full_all.cu and patched kernel_generated.link.cu are written",
    )
    parser.add_argument(
        "--validate-llvm",
        action="store_true",
        help="Parse emitted LLVM IR with llvmlite if available",
    )
    parser.add_argument(
        "--emit-ptx",
        action="store_true",
        help="Compile emitted LLVM IR to kernel_generated.full_all.ptx with clang",
    )
    parser.add_argument(
        "--validate-ptx",
        action="store_true",
        help="Assemble emitted PTX with ptxas; implies --emit-ptx",
    )
    parser.add_argument(
        "--emit-hsaco",
        action="store_true",
        help="Compile emitted LLVM IR to kernel_generated.full_all.hsaco with clang/ld.lld",
    )
    parser.add_argument(
        "--clang-path",
        default="clang",
        help="clang executable used for LLVM IR to PTX compilation",
    )
    parser.add_argument(
        "--ld-lld-path",
        default=shutil.which("ld.lld") or "ld.lld",
        help="ld.lld executable used for LLVM IR to hsaco linking",
    )
    parser.add_argument(
        "--ptxas-path",
        default="ptxas",
        help="ptxas executable used for PTX validation",
    )
    parser.add_argument(
        "--cuda-arch",
        default=None,
        help="Optional CUDA GPU arch, for example sm_80",
    )
    parser.add_argument(
        "--llvm-backend-target",
        choices=("nvptx", "rocdl"),
        default="nvptx",
        help="Explicit LLVM lowering target.",
    )
    parser.add_argument(
        "--gfx-arch",
        default="",
        help="Target gfx arch for --emit-hsaco (for example gfx1201)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_ROOT,
        help="Directory for reusing base full_all artifacts across identical full_comb/full_seq inputs",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable the base full_all artifact cache",
    )
    return parser.parse_args()


def _validate_llvm_ir(ir_text: str) -> None:
    try:
        import llvmlite.binding as llvm
    except ImportError as exc:
        raise RuntimeError("--validate-llvm requested but llvmlite is unavailable") from exc
    llvm.parse_assembly(ir_text)


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    cache_entry_dir: Path | None = None
    cache_hit = False
    if not args.no_cache:
        cache_key = _compute_base_cache_key(
            full_comb_path=args.full_comb,
            full_seq_path=args.full_seq,
            llvm_backend_target=args.llvm_backend_target,
        )
        cache_entry_dir = args.cache_dir / cache_key
        if _base_cache_entry_ready(cache_entry_dir):
            _restore_base_artifacts(cache_entry_dir, args.out_dir)
            cache_hit = True
            print(f"full_kernel_fuser_cache hit=1 key={cache_key}")

    llvm_path = args.out_dir / "kernel_generated.full_all.ll"
    if not cache_hit:
        comb = load_kernel(args.full_comb, "sim_accel_eval_assignw_u32_full_comb")
        seq = load_kernel(args.full_seq, "sim_accel_eval_assignw_u32_full_seq")
        fused = merge_kernels(comb, seq)
        full_all_text = emit_cuda_kernel(fused, "sim_accel_eval_assignw_u32_full_all")
        llvm_text = emit_llvm_ir(
            fused,
            "sim_accel_eval_assignw_u32_full_all",
            backend_target=args.llvm_backend_target,
        )
        (args.out_dir / "kernel_generated.full_all.cu").write_text(full_all_text, encoding="utf-8")
        (args.out_dir / "kernel_generated.full_all.ssa").write_text(
            emit_ssa_kernel(fused, "sim_accel_eval_assignw_u32_full_all"), encoding="utf-8"
        )
        llvm_path.write_text(llvm_text, encoding="utf-8")
        backend_json = {
            "llvm_backend_target": args.llvm_backend_target,
            "compiler_backend": ("nvptx" if args.llvm_backend_target == "nvptx" else "rocdl"),
            "ptx_compatible": args.llvm_backend_target == "nvptx",
            "hsaco_compatible": args.llvm_backend_target == "rocdl",
        }
        (args.out_dir / "kernel_generated.full_all.backend.json").write_text(
            json.dumps(backend_json, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if cache_entry_dir is not None:
            _populate_base_cache(
                cache_entry_dir,
                args.out_dir,
                metadata={
                    "cache_format_version": CACHE_FORMAT_VERSION,
                    "script_sha256": _script_cache_salt(),
                    "llvm_backend_target": args.llvm_backend_target,
                    "full_comb_path": str(args.full_comb),
                    "full_seq_path": str(args.full_seq),
                    "full_comb_sha256": _sha256_file(args.full_comb),
                    "full_seq_sha256": _sha256_file(args.full_seq),
                },
            )
            print(f"full_kernel_fuser_cache hit=0 key={cache_entry_dir.name}")
    else:
        llvm_text = llvm_path.read_text(encoding="utf-8")

    if args.validate_llvm:
        _validate_llvm_ir(llvm_text)
    if args.emit_ptx or args.validate_ptx:
        if args.llvm_backend_target != "nvptx":
            raise RuntimeError("--emit-ptx/--validate-ptx require --llvm-backend-target nvptx")
        ptx_path = args.out_dir / "kernel_generated.full_all.ptx"
        emit_ptx(
            llvm_path,
            ptx_path,
            clang_path=args.clang_path,
            cuda_arch=args.cuda_arch,
        )
        print(f"wrote {ptx_path}")
        if args.validate_ptx:
            cubin_path = validate_ptx(ptx_path, ptxas_path=args.ptxas_path, cuda_arch=args.cuda_arch)
            print(f"validated {cubin_path}")
    if args.emit_hsaco:
        if args.llvm_backend_target != "rocdl":
            raise RuntimeError("--emit-hsaco requires --llvm-backend-target rocdl")
        if not args.gfx_arch:
            raise RuntimeError("--emit-hsaco requires --gfx-arch")
        hsaco_path = args.out_dir / "kernel_generated.full_all.hsaco"
        emit_hsaco(
            llvm_path,
            hsaco_path,
            clang_path=args.clang_path,
            ld_lld_path=args.ld_lld_path,
            gfx_arch=args.gfx_arch,
        )
        print(f"wrote {hsaco_path}")

    link_text = args.link.read_text(encoding="utf-8")
    state_var_count = _infer_state_var_count(link_text)
    patched_link = patch_link_source(link_text, state_var_count)
    (args.out_dir / "kernel_generated.link.cu").write_text(patched_link, encoding="utf-8")

    print(f"wrote {(args.out_dir / 'kernel_generated.full_all.cu')}")
    print(f"wrote {(args.out_dir / 'kernel_generated.full_all.ssa')}")
    print(f"wrote {(args.out_dir / 'kernel_generated.full_all.ll')}")
    print(f"wrote {(args.out_dir / 'kernel_generated.full_all.backend.json')}")
    print(f"wrote {(args.out_dir / 'kernel_generated.link.cu')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
