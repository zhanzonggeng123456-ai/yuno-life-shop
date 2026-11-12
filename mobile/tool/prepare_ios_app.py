#!/usr/bin/env python3
"""Normalize local iOS bundle permissions without changing signed content.

Run on the built .app before installation. This does not repair a revoked
certificate or authorize an unprovisioned device; codesign must still verify.
"""
import argparse
from pathlib import Path
import subprocess


def normalize_permissions(bundle: Path) -> None:
    for path in [bundle, *bundle.rglob("*")]:
        if path.is_symlink():
            continue
        if path.is_dir():
            path.chmod(0o755)
        elif path.is_file():
            path.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    args = parser.parse_args()
    app = args.app.resolve(strict=True)
    if app.suffix != ".app" or not (app / "embedded.mobileprovision").is_file():
        parser.error("Expected a signed physical-device iOS .app bundle")
    normalize_permissions(app)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    print("Bundle permissions normalized; code signature verified.")


if __name__ == "__main__":
    main()
