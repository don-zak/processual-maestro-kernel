#!/usr/bin/env python3
"""Fail-closed static integrity audit for production Python sources.

This complements linters and Bandit with repository-specific checks for silent
exception swallowing and dangerous runtime primitives that can hide in rarely
executed paths.
"""
from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path

ROOTS = ("processual_kernel", "cgtlib", "processual_api")

# Narrowly documented best-effort/fail-closed boundaries. These functions must
# never grant authority or persist secrets when the guarded operation fails.
SILENT_EXCEPTION_ALLOWLIST = {
    # Capacity accounting attribution only; authentication occurs elsewhere.
    ("processual_api/middleware/runtime_capacity.py", "_request_actor_key"),
    # Invalid JWT attribution fails closed to no subscription customer ref.
    ("processual_api/middleware/subscription.py", "_extract_customer_ref"),
    # Observability must never break the application it observes.
    ("processual_kernel/observability/sentry.py", "capture_exception"),
    ("processual_kernel/observability/sentry.py", "capture_message"),
    # Best-effort cleanup of local diagnostic state.
    ("processual_api/cgt_governor/data/storage.py", "clear"),
    ("processual_api/cgt_governor/data/telemetry_storage.py", "clear"),
    # Metrics are non-authoritative and must not break orchestration.
    ("processual_api/cgt_governor/policy/orchestration_metrics.py", "record_orchestration"),
    # Corrupt historical statement entries are skipped while listing; writes
    # and authority decisions are not performed by this function.
    ("processual_api/billing/customer_billing_statements.py", "list_statements"),
}


@dataclass(frozen=True, slots=True)
class Finding:
    path: str
    line: int
    rule: str
    detail: str


def _name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _is_true(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _is_false(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _silently_swallows(body: list[ast.stmt]) -> bool:
    if not body:
        return True
    for stmt in body:
        if isinstance(stmt, (ast.Pass, ast.Continue, ast.Break)):
            continue
        if isinstance(stmt, ast.Return) and (
            stmt.value is None
            or (isinstance(stmt.value, ast.Constant) and stmt.value.value is None)
        ):
            continue
        return False
    return True


class Auditor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.findings: list[Finding] = []
        self.functions: list[str] = []

    @property
    def function(self) -> str:
        return self.functions[-1] if self.functions else "<module>"

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(node.name)
        self.generic_visit(node)
        self.functions.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.functions.append(node.name)
        self.generic_visit(node)
        self.functions.pop()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        exception_name = _name(node.type) if node.type is not None else "bare"
        broad = node.type is None or exception_name in {"Exception", "BaseException"}
        if broad and _silently_swallows(node.body):
            if (self.path, self.function) not in SILENT_EXCEPTION_ALLOWLIST:
                self.findings.append(
                    Finding(
                        self.path,
                        node.lineno,
                        "silent-broad-exception",
                        f"{self.function}: except {exception_name} silently swallows failure",
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = _name(node.func)
        if call_name in {"eval", "exec", "os.system", "pickle.loads", "marshal.loads"}:
            self.findings.append(Finding(self.path, node.lineno, "dangerous-call", call_name))

        if call_name.startswith("subprocess."):
            for keyword in node.keywords:
                if keyword.arg == "shell" and _is_true(keyword.value):
                    self.findings.append(
                        Finding(
                            self.path,
                            node.lineno,
                            "subprocess-shell",
                            f"{call_name}(..., shell=True)",
                        )
                    )

        if call_name.startswith(("requests.", "httpx.")):
            for keyword in node.keywords:
                if keyword.arg == "verify" and _is_false(keyword.value):
                    self.findings.append(
                        Finding(
                            self.path,
                            node.lineno,
                            "tls-verification-disabled",
                            f"{call_name}(..., verify=False)",
                        )
                    )

        if call_name == "yaml.load":
            has_safe_loader = any(
                keyword.arg == "Loader"
                and _name(keyword.value) in {"SafeLoader", "yaml.SafeLoader"}
                for keyword in node.keywords
            )
            if not has_safe_loader:
                self.findings.append(
                    Finding(
                        self.path,
                        node.lineno,
                        "unsafe-yaml-load",
                        "yaml.load without SafeLoader",
                    )
                )
        self.generic_visit(node)


def audit(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for package in ROOTS:
        package_root = root / package
        for path in sorted(package_root.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            try:
                # utf-8-sig accepts both ordinary UTF-8 and legacy BOM-prefixed
                # sources, matching Python's source-decoding behavior.
                source = path.read_text(encoding="utf-8-sig")
                tree = ast.parse(source, filename=relative)
            except (OSError, UnicodeError, SyntaxError) as exc:
                line = getattr(exc, "lineno", 0) or 0
                detail = f"{type(exc).__name__}: {exc}"
                findings.append(Finding(relative, line, "parse-failure", detail))
                continue
            auditor = Auditor(relative)
            auditor.visit(tree)
            findings.extend(auditor.findings)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()

    findings = audit(Path(args.root).resolve())
    payload = {
        "schema_version": 1,
        "roots": list(ROOTS),
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
