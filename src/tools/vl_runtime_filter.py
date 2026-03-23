"""
vl_runtime_filter.py
Verilator 生成コードの GPU 実行可否を判定する。

- is_runtime(): GPU で実行できない関数かどうかを判定
- detect_vlsyms_offset(): vlSymsp フィールドのバイトオフセットを TBAA から検出
"""

import re

# GPU で stub 化すべき Verilated ランタイム / C++ 標準ライブラリのプレフィックス
_RUNTIME_PREFIXES = (
    '_ZN9Verilated',        # Verilated::* クラスメソッド
    '_ZNK9Verilated',
    '_ZN16VerilatedContext',
    '_ZNK16VerilatedContext',
    '_ZN14VerilatedModel',
    '_ZNK14VerilatedModel',
    '_ZN9VlDeleter',
    '_ZNSt',                # std::* (string, exception etc.)
    '_ZSt',
    '_Z13sc_time_stamp',
    '_Z15vl_time_stamp',
    '__cxa_',
    '_ZTHN',                # TLS variable helper
)

# vlSyms を参照するがシミュレーション本体の関数 → stub 化しない
# fake_syms_buf による null-safe 化で対応する
_FORCE_INCLUDE_PATTERNS = (
    '___ico_sequent',
    '___nba_comb',
)


def is_runtime(name: str, func_body: str) -> bool:
    """
    GPU で実行できない関数なら True を返す。

    stub 化の判定基準:
    1. _FORCE_INCLUDE_PATTERNS に一致 → 必ず False (GPU に含める)
    2. _RUNTIME_PREFIXES に一致 → True
    3. static guard (@_ZGVZ) を参照 → True
    4. VerilatedSyms / _Syms を参照 → True
    """
    if any(pat in name for pat in _FORCE_INCLUDE_PATTERNS):
        return False
    if any(name.startswith(p) for p in _RUNTIME_PREFIXES):
        return True
    if re.search(r'@_ZGVZ', func_body):
        return True
    if re.search(r'VerilatedSyms|_gpu_cov_tb__Syms', func_body):
        return True
    return False


def detect_vlsyms_offset(text: str) -> int | None:
    """
    TBAA メタデータから vlSymsp フィールドのバイトオフセットを検出する。
    root class の TBAA ノードで "any pointer" 型が現れる最初のオフセットが vlSymsp。
    例: !10 = !{!"..._024root", ..., !31, i64 2000, !31, i64 2008}  → 2000
    """
    m = re.search(r'^(!(\d+))\s*=\s*!\{!"any pointer"', text, re.MULTILINE)
    if not m:
        return None
    any_ptr_id = m.group(2)
    pat = re.compile(
        r'^!\d+\s*=\s*!\{!"[^"]*_024root".*?!'
        + re.escape(any_ptr_id) + r',\s*i64\s+(\d+)',
        re.MULTILINE,
    )
    m2 = pat.search(text)
    if m2:
        return int(m2.group(1))
    return None
