import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import cgtlib


def test_public_fallback_stable_api_does_not_traverse_api_or_private_imports(tmp_path: Path):
    source_package = Path(cgtlib.__file__).resolve().parent
    stripped_root = tmp_path / "public-strip"
    shutil.copytree(
        source_package,
        stripped_root / "cgtlib",
        ignore=shutil.ignore_patterns("private", "__pycache__", "*.pyc", "pyproject.toml"),
    )

    probe = textwrap.dedent(
        """
        import json
        import sys

        sys.path.insert(0, sys.argv[1])
        import cgtlib
        from cgtlib._stable_api import CGTLIB_STABLE_API as declared_stable_api

        print(
            json.dumps(
                {
                    "has_private": cgtlib._HAS_PRIVATE,
                    "stable_api_is_tuple": isinstance(cgtlib.CGTLIB_STABLE_API, tuple),
                    "stable_api_matches_declaration": cgtlib.CGTLIB_STABLE_API == declared_stable_api,
                    "stable_api_contains_manifest": "build_cgtlib_manifest" in cgtlib.CGTLIB_STABLE_API,
                    "api_module_loaded": "cgtlib.api" in sys.modules,
                    "private_module_loaded": "cgtlib.private" in sys.modules,
                }
            )
        )
        """
    )

    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", probe, str(stripped_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload == {
        "has_private": False,
        "stable_api_is_tuple": True,
        "stable_api_matches_declaration": True,
        "stable_api_contains_manifest": True,
        "api_module_loaded": False,
        "private_module_loaded": False,
    }
