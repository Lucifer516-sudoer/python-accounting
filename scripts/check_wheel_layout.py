#!/usr/bin/env python
"""
Verify that the built wheel keeps `config.toml` at its root.

This is not a cosmetic packaging check: `python_accounting/config.py` resolves the
config as `<package>/../config.toml`, i.e. from the *root* of site-packages. If a
build backend change ever moves config.toml inside the package, the library still
imports fine from a source checkout and silently breaks for everyone who pip
installs it. The source tree cannot catch that, so this does.

Exits 0 if the layout is correct, 1 otherwise.
"""

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def build_wheel(out_dir: Path) -> Path:
    """Build a wheel into out_dir and return a path to it."""
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv not found on PATH; cannot build the wheel to check it.")

    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(out_dir)],
        check=True,
        capture_output=True,
    )
    wheels = list(out_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one wheel, got {len(wheels)}")
    return wheels[0]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        wheel = build_wheel(Path(tmp))
        names = zipfile.ZipFile(wheel).namelist()

    if "config.toml" not in names:
        print("config.toml is NOT at the wheel root.", file=sys.stderr)
        print(
            "python_accounting.config will fail to find it once installed.",
            file=sys.stderr,
        )
        print(
            f"wheel contents: {sorted(n for n in names if '/' not in n)}",
            file=sys.stderr,
        )
        return 1

    if "python_accounting/__init__.py" in names:
        print(
            "python_accounting/__init__.py exists; the package is a namespace "
            "package by design (removed in a859be1).",
            file=sys.stderr,
        )
        return 1

    print(f"wheel layout OK: config.toml at root of {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
