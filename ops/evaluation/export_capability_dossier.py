"""Export the synthetic-only capability dossier as auditable JSON + standalone HTML.

Requires running inside the reviewed public repository. Never fetches live data,
writes authority state, or calls the Workspace. The HTML embeds exactly the
same recorded results as the canonical JSON payload.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess

from ops.evaluation.capability_cases import build

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "docs" / "capability-evidence" / "template.html"
MARKER = "/*__MAESTRO_EVIDENCE_JSON__*/"

def verified_source_sha() -> str:
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         text=True, capture_output=True, timeout=5, check=True).stdout.strip()
    if len(sha) != 40 or any(x not in "0123456789abcdef" for x in sha):
        raise RuntimeError("Invalid source revision")
    return sha

def write(output: Path, evidence: dict) -> dict:
    if evidence["total"] != 16 or evidence["passed"] != 16:
        raise RuntimeError("Not all 16 internal scenarios passed; refusing dossier export")
    output.mkdir(parents=True, exist_ok=True)
    json_bytes = (json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    (output / "results.json").write_bytes(json_bytes)
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(MARKER) != 1:
        raise RuntimeError("Ambiguous or missing evidence template marker")
    embedded = json.dumps(evidence, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).replace("<", "\\u003c").replace(
                          ">", "\\u003e").replace("&", "\\u0026")
    viewer = template.replace(MARKER, "const EVIDENCE = " + embedded + ";")
    (output / "index.html").write_text(viewer, encoding="utf-8")
    manifest = {
        "schema_version": "maestro-capability-manifest-v1",
        "source_sha": evidence["source_sha"],
        "results_sha256": hashlib.sha256(json_bytes).hexdigest(),
        "viewer_sha256": hashlib.sha256(viewer.encode()).hexdigest(),
        "case_count": evidence["total"],
        "verified_count": evidence["passed"],
        "external_http_calls": 0,
        "workspace_execution_proved": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("capability-evidence-output"))
    args = parser.parse_args()
    data = asyncio.run(build())
    data["source_sha"] = verified_source_sha()
    data["limitations"] = [
        "Internal tests invoke real CGT policy and Maestro on synthetic hash-only input.",
        "No live sandbox HTTP, real customer data, Evaluation API key or Neon quota was used.",
        "Fate Vector encodes preset CGT policy signals, not validated predictive performance.",
        "Match any future Workspace execution to an independently verified, redacted live receipt.",
    ]
    manifest = write(args.output, data)
    print(json.dumps({"total": data["total"], "passed": data["passed"],
                      "scope": "INTERNAL_SYNTHETIC_ONLY",
                      "output_dir": str(args.output),
                      "source_sha": manifest["source_sha"]}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
