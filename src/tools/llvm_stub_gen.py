"""
llvm_stub_gen.py
LLVM IR の declare シグニチャから no-op stub define を生成する。
"""

import re


def _parse_param_list(text: str, name: str) -> tuple[str, str] | None:
    """
    'declare RETTYPE @name(PARAMS)' から (ret_type, params_body) を返す。
    PARAMS 内のネスト括弧 (dereferenceable(N) 等) に対応する。
    """
    pat = re.compile(r'declare\s+([^\n]*?)\s+@' + re.escape(name) + r'\s*\(')
    m = pat.search(text)
    if not m:
        return None
    ret_type = m.group(1).strip()
    pos = m.end()

    depth = 1
    end = pos
    while end < len(text) and depth > 0:
        c = text[end]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        end += 1
    params_body = text[pos:end - 1]
    return ret_type, params_body


def _clean_param_type(raw: str) -> str:
    """パラメータ型/戻り値型から LLVM 属性・リンケージ指定子を除去して型だけ残す"""
    t = re.sub(r'\bdereferenc\w+\(\d+\)', '', raw)
    for kw in ('noundef', 'nonnull', 'readonly', 'writeonly', 'nocapture',
               'returned', 'noalias', 'zeroext', 'signext', 'inreg',
               'byref', 'byval', 'sret', 'swiftself', 'swifterror',
               'extern_weak', 'local_unnamed_addr', 'unnamed_addr',
               'dso_local', 'dso_preemptable'):
        t = re.sub(r'\b' + kw + r'\b', '', t)
    t = re.sub(r'\balign\s+\d+\b', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def make_no_op_stub(mangled_name: str, text: str) -> str:
    """declare からシグニチャを取得して no-op define を生成"""
    parsed = _parse_param_list(text, mangled_name)
    if not parsed:
        return (f'define void @{mangled_name}('
                f'ptr %0, i32 %1, ptr %2, ptr %3) {{\n  ret void\n}}\n')
    ret_type, params_body = parsed
    ret_type = _clean_param_type(ret_type)

    param_types = []
    depth = 0
    cur: list[str] = []
    for ch in params_body + ',':
        if ch == ',' and depth == 0:
            tok = ''.join(cur).strip()
            if tok:
                param_types.append(_clean_param_type(tok))
            cur = []
        else:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            cur.append(ch)

    named = []
    idx = 0
    for t in param_types:
        if not t:
            continue
        if t == '...':
            named.append('...')
        else:
            named.append(f'{t} %p{idx}')
            idx += 1
    param_list = ', '.join(named)

    if ret_type == 'void':
        ret_stmt = 'ret void'
    elif 'i1' in ret_type:
        ret_stmt = 'ret i1 false'
    elif 'i32' in ret_type:
        ret_stmt = 'ret i32 0'
    elif 'i64' in ret_type:
        ret_stmt = 'ret i64 0'
    elif ret_type == 'ptr':
        ret_stmt = 'ret ptr null'
    elif 'double' in ret_type or 'float' in ret_type:
        ret_stmt = f'ret {ret_type} 0.0'
    else:
        ret_stmt = f'ret {ret_type} undef'

    return f'define {ret_type} @{mangled_name}({param_list}) {{\n  {ret_stmt}\n}}\n'
