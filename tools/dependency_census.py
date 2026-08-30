#!/usr/bin/env python3
"""Deterministic dependency census for Maestro's current Python package boundaries.

This tool is intentionally stdlib-only and read-only. It inventories Python files,
byte sizes, import roots, and internal package edges without importing project code.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PACKAGE_ROOTS = ("processual_kernel", "cgtlib", "processual_api")


@dataclass(frozen=True)
class FileRecord:
    path: str
    package: str
    bytes: int
    imports: tuple[str, ...]
    internal_edges: tuple[str, ...]


def _module_root(name: str | None) -> str | None:
    if not name:
        return None
    return name.split(".", 1)[0]


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _module_root(alias.name)
                if root:
                    roots.add(root)
        elif isinstance(node, ast.ImportFrom):
            root = _module_root(node.module)
            if root:
                roots.add(root)
    return tuple(sorted(roots))


def _iter_python_files(repo_root: Path) -> Iterable[tuple[str, Path]]:
    for package in PACKAGE_ROOTS:
        package_root = repo_root / package
        if not package_root.is_dir():
            continue
        for path in sorted(package_root.rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield package, path


def census(repo_root: Path) -> dict[str, object]:
    records: list[FileRecord] = []
    package_bytes: Counter[str] = Counter()
    package_files: Counter[str] = Counter()
    import_roots: Counter[str] = Counter()
    internal_edges: Counter[tuple[str, str]] = Counter()

    for package, path in _iter_python_files(repo_root):
        roots = _imports(path)
        edges = tuple(sorted(root for root in roots if root in PACKAGE_ROOTS and root != package))
        relative = path.relative_to(repo_root).as_posix()
        size = path.stat().st_size
        records.append(FileRecord(relative, package, size, roots, edges))
        package_bytes[package] += size
        package_files[package] += 1
        import_roots.update(roots)
        internal_edges.update((package, target) for target in edges)

    return {
        "schema_version": 1,
        "packages": {
            package: {
                "python_files": package_files[package],
                "python_bytes": package_bytes[package],
            }
            for package in PACKAGE_ROOTS
        },
        "totals": {
            "python_files": sum(package_files.values()),
            "python_bytes": sum(package_bytes.values()),
        },
        "internal_edges": [
            {"from": source, "to": target, "files": count}
            for (source, target), count in sorted(internal_edges.items())
        ],
        "import_roots": [
            {"root": root, "files": count}
            for root, count in sorted(import_roots.items())
        ],
        "files": [
            {
                "path": record.path,
                "package": record.package,
                "bytes": record.bytes,
                "imports": list(record.imports),
                "internal_edges": list(record.internal_edges),
            }
            for record in records
        ],
    }


def render_markdown(data: dict[str, object]) -> str:
    packages = data["packages"]
    totals = data["totals"]
    edges = data["internal_edges"]
    lines = [
        "# Maestro Dependency Census",
        "",
        "Generated deterministically from Python source files; project modules are not imported.",
        "",
        "## Package inventory",
        "",
        "| Package | Python files | Python bytes |",
        "| --- | ---: | ---: |",
    ]
    assert isinstance(packages, dict)
    for package in PACKAGE_ROOTS:
        stats = packages[package]
        assert isinstance(stats, dict)
        lines.append(f"| `{package}` | {stats['python_files']} | {stats['python_bytes']} |")
    assert isinstance(totals, dict)
    lines.extend(
        [
            f"| **Total** | **{totals['python_files']}** | **{totals['python_bytes']}** |",
            "",
            "## Internal package edges",
            "",
            "| From | To | Files with edge |",
            "| --- | --- | ---: |",
        ]
    )
    assert isinstance(edges, list)
    if edges:
        for edge in edges:
            assert isinstance(edge, dict)
            lines.append(f"| `{edge['from']}` | `{edge['to']}` | {edge['files']} |")
    else:
        lines.append("| _none_ | _none_ | 0 |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="write output to this file instead of stdout")
    args = parser.parse_args()

    data = census(args.root.resolve())
    if args.format == "json":
        rendered = json.dumps(data, indent=2, sort_keys=True) + "\n"
    else:
        rendered = render_markdown(data) + "\n"

    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
