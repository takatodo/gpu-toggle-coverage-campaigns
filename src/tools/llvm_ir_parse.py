"""
llvm_ir_parse.py
LLVM IR テキストからデータ構造を抽出するパーサ群。
副作用なし、テキスト → dict/set/tuple のみ。
"""

import re

_CALL_PAT = re.compile(r'(?:call|tail call|invoke)[^@\n]*@([\w.]+)')


def extract_functions(text: str) -> dict[str, str]:
    """全 define 関数を {name: full_text} で返す"""
    funcs = {}
    i = 0
    lines = text.splitlines(keepends=True)
    n = len(lines)
    while i < n:
        line = lines[i]
        m = re.match(r'^define[^@\n]*@(\w+)', line)
        if m:
            name = m.group(1)
            body_lines = [line]
            depth = line.count('{') - line.count('}')
            i += 1
            while i < n and depth > 0:
                body_lines.append(lines[i])
                depth += lines[i].count('{') - lines[i].count('}')
                i += 1
            funcs[name] = ''.join(body_lines)
        else:
            i += 1
    return funcs


def reachable_from(start: str, funcs: dict[str, str]) -> set[str]:
    """start から call/invoke で到達できる全関数名 (define 済みのみ)"""
    visited: set[str] = set()
    queue = [start]
    while queue:
        fn = queue.pop()
        if fn in visited:
            continue
        visited.add(fn)
        body = funcs.get(fn, '')
        for callee in _CALL_PAT.findall(body):
            if callee in funcs and callee not in visited:
                queue.append(callee)
    return visited


def external_calls(names: set[str], funcs: dict[str, str]) -> set[str]:
    """names の関数群から呼ばれる、funcs に定義のない外部関数"""
    ext: set[str] = set()
    for fn in names:
        body = funcs.get(fn, '')
        for callee in _CALL_PAT.findall(body):
            if callee not in funcs and not callee.startswith('llvm.'):
                ext.add(callee)
    return ext


