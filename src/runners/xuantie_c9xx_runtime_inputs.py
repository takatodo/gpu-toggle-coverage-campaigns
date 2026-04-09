from __future__ import annotations

from pathlib import Path


def ensure_runtime_pat_pair(
    *,
    mdir: Path,
    inst_pat: Path,
    data_pat: Path,
) -> dict[str, Path]:
    staged: dict[str, Path] = {}
    for dest_name, source_path in (
        ("inst.pat", inst_pat),
        ("data.pat", data_pat),
    ):
        source = source_path.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"runtime {dest_name} not found: {source}")
        dest = mdir / dest_name
        if dest.is_symlink():
            if dest.resolve() == source:
                staged[dest_name] = source
                continue
            dest.unlink()
        elif dest.exists():
            dest.unlink()
        dest.symlink_to(source)
        staged[dest_name] = source
    return staged
