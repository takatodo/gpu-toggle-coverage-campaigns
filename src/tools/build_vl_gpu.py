#!/usr/bin/env python3
"""
build_vl_gpu.py
Verilator --cc 出力ディレクトリから GPU cubin を自動生成する。

Usage:
  python3 build_vl_gpu.py <mdir> [--sm sm_89] [--out out.cubin] [--force]

Steps:
  1. {mdir}/*_classes.mk から VM_CLASSES_FAST + VM_CLASSES_SLOW を読み込む
  2. 各 .cpp を clang++-18 -S -emit-llvm -O1 → .ll
  3. llvm-link-18 → merged.ll
  4. C++ probe で storage_size (sizeof root struct) を自動検出
  5. vlgpugen merged.ll --storage-size=N → vl_batch_gpu.ll
  6. opt (lowerinvoke,simplifycfg,vl-strip-x86-attrs,vl-patch-convergence) → patched
  7. opt -O3 → vl_batch_gpu_opt.ll → llc-18 → vl_batch_gpu.ptx → ptxas → vl_batch_gpu.cubin
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR  = Path(__file__).parent
PASSES_DIR  = SCRIPT_DIR.parent / 'passes'
PASSES_SO   = PASSES_DIR / 'VlGpuPasses.so'
VLGPUGEN    = PASSES_DIR / 'vlgpugen'

VL_INCLUDE = Path('/usr/local/share/verilator/include')

CLANG    = 'clang++-18'
LLVMLINK = 'llvm-link-18'
OPT      = 'opt-18'
LLC      = 'llc-18'
PTXAS    = 'ptxas'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: list, **kwargs):
    print(' '.join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kwargs)


def read_mk_list(mk_text: str, var: str) -> list[str]:
    """Makefile の var += ... (複数行) を収集して値リストを返す"""
    values = []
    in_var = False
    for raw_line in mk_text.splitlines():
        line = raw_line.strip()
        if not in_var:
            m = re.match(r'^' + re.escape(var) + r'\s*\+?=\s*(.*)', line)
            if m:
                in_var = True
                val = m.group(1).rstrip('\\').strip()
                if val:
                    values.append(val)
        else:
            val = line.rstrip('\\').strip()
            if val:
                values.append(val)
            if not raw_line.rstrip().endswith('\\'):
                in_var = False
    return values


def find_classes_mk(mdir: Path) -> Path:
    hits = list(mdir.glob('*_classes.mk'))
    if not hits:
        raise FileNotFoundError(f'No *_classes.mk found in {mdir}')
    return hits[0]


def find_prefix(mdir: Path) -> str:
    mk = find_classes_mk(mdir)
    return mk.stem.replace('_classes', '')


# ---------------------------------------------------------------------------
# Storage size detection via C++ probe
# ---------------------------------------------------------------------------

def detect_storage_size(mdir: Path, prefix: str) -> int:
    """sizeof(prefix___024root) を C++ probe でコンパイル実行して返す"""
    root_h = mdir / f'{prefix}___024root.h'
    probe_src = (
        f'#include <cstdio>\n'
        f'#include "{root_h.resolve()}"\n'
        f'int main() {{\n'
        f'    printf("%zu\\n", sizeof({prefix}___024root));\n'
        f'    return 0;\n'
        f'}}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / 'probe_size.cpp'
        exe = Path(tmp) / 'probe_size'
        src.write_text(probe_src)
        cmd = [
            CLANG, '-std=c++17',
            f'-I{mdir}', f'-I{VL_INCLUDE}',
            str(src), '-o', str(exe),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
        return int(result.stdout.strip())


# ---------------------------------------------------------------------------
# Compile .cpp → .ll
# ---------------------------------------------------------------------------

def compile_ll(cpp_path: Path, mdir: Path, out_ll: Path):
    cmd = [
        CLANG, '-std=c++17', '-S', '-emit-llvm', '-O1',
        f'-I{mdir}', f'-I{VL_INCLUDE}',
        str(cpp_path), '-o', str(out_ll),
    ]
    run(cmd)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_vl_gpu(
    mdir: Path,
    sm: str = 'sm_89',
    out_cubin: Path = None,
    force: bool = False,
) -> tuple[Path, int]:

    mdir = mdir.resolve()
    classes_mk = find_classes_mk(mdir)
    mk_text = classes_mk.read_text()
    prefix = find_prefix(mdir)
    print(f'[build_vl_gpu] mdir={mdir}  prefix={prefix}  sm={sm}')

    fast_classes = read_mk_list(mk_text, 'VM_CLASSES_FAST')
    slow_classes = read_mk_list(mk_text, 'VM_CLASSES_SLOW')
    all_classes  = fast_classes + slow_classes
    print(f'  Classes: {all_classes}')

    # Step 1: compile each .cpp → .ll
    ll_files = []
    for cls in all_classes:
        cpp = mdir / f'{cls}.cpp'
        if not cpp.exists():
            print(f'  skip (missing): {cpp.name}')
            continue
        out_ll = mdir / f'{cls}.ll'
        if force or not out_ll.exists():
            print(f'  [clang] {cpp.name} → {out_ll.name}')
            compile_ll(cpp, mdir, out_ll)
        else:
            print(f'  [cached] {out_ll.name}')
        ll_files.append(out_ll)

    if not ll_files:
        raise RuntimeError('No .ll files generated')

    # Step 2: llvm-link → merged.ll
    merged_ll = mdir / 'merged.ll'
    if force or not merged_ll.exists():
        print(f'  [llvm-link] → merged.ll')
        run([LLVMLINK, '-S', '-o', str(merged_ll)] + [str(f) for f in ll_files])
    else:
        print(f'  [cached] merged.ll')

    # Step 3: detect storage_size
    print('  [probe] detecting storage_size...')
    storage_size = detect_storage_size(mdir, prefix)
    print(f'  storage_size = {storage_size} bytes')

    # Step 4: vlgpugen merged.ll → vl_batch_gpu.ll
    gpu_ll = mdir / 'vl_batch_gpu.ll'
    print('  [vlgpugen] → vl_batch_gpu.ll')
    run([str(VLGPUGEN), str(merged_ll),
         f'--storage-size={storage_size}', f'--out={gpu_ll}'])

    # Step 5a: VlGpuPasses.so のビルド (変更がなければ no-op)
    run(['make', '-C', str(PASSES_DIR), '--no-print-directory'])
    # Step 5b: EH lowering + x86 属性除去 + 収束パッチ
    gpu_patched = mdir / 'vl_batch_gpu_patched.ll'
    print('  [opt] lowerinvoke,simplifycfg,vl-strip-x86-attrs,vl-patch-convergence')
    vl_passes = 'lowerinvoke,simplifycfg,vl-strip-x86-attrs,vl-patch-convergence'
    run([OPT, f'--load-pass-plugin={PASSES_SO}',
         f'-passes={vl_passes}', '-S', str(gpu_ll), '-o', str(gpu_patched)])
    # Step 5c: O3 最適化
    gpu_opt = mdir / 'vl_batch_gpu_opt.ll'
    print('  [opt -O3] → vl_batch_gpu_opt.ll')
    run([OPT, '-O3', '-S', str(gpu_patched), '-o', str(gpu_opt)])

    # Step 6: llc → ptx
    gpu_ptx = mdir / 'vl_batch_gpu.ptx'
    print(f'  [llc] -march=nvptx64 -mcpu={sm} → vl_batch_gpu.ptx')
    run([LLC, '-march=nvptx64', f'-mcpu={sm}', str(gpu_opt), '-o', str(gpu_ptx)])

    # Step 7: ptxas → cubin
    if out_cubin is None:
        out_cubin = mdir / 'vl_batch_gpu.cubin'
    print(f'  [ptxas] → {out_cubin.name}')
    run([PTXAS, f'--gpu-name={sm}', str(gpu_ptx), '-o', str(out_cubin)])

    sz = out_cubin.stat().st_size
    print(f'\nDone: {out_cubin}  ({sz} bytes)  storage_size={storage_size}')
    return out_cubin, storage_size


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description='Verilator --cc output dir → GPU cubin'
    )
    p.add_argument('mdir', help='Verilator --cc output directory (contains *_classes.mk)')
    p.add_argument('--sm', default='sm_89', help='GPU arch (default: sm_89)')
    p.add_argument('--out', default=None, help='Output cubin path (default: mdir/vl_batch_gpu.cubin)')
    p.add_argument('--force', action='store_true', help='Re-run all steps even if outputs exist')
    args = p.parse_args()

    cubin, sz = build_vl_gpu(
        Path(args.mdir),
        sm=args.sm,
        out_cubin=Path(args.out) if args.out else None,
        force=args.force,
    )
    print(f'\nstorage_size={sz}')
    print(f'cubin={cubin}')


if __name__ == '__main__':
    main()
