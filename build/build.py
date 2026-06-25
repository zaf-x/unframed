"""
Build script for PyInstaller.

Usage:
    pip install pyinstaller
    python build/build.py

Output:
    dist/unframed/         # Directory with all dependencies
    dist/unframed.exe      # Windows executable (on Windows)
    dist/unframed          # Linux/macOS executable
"""

import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SPEC = ROOT / "build" / "unframed.spec"


def main():
    # Ensure seeds/ and docs/ are included
    data_args = []
    seeds_dir = ROOT / "seeds"
    docs_dir = ROOT / "docs"

    if seeds_dir.is_dir():
        data_args.append(f"--add-data={seeds_dir}{os.pathsep}seeds")
    if docs_dir.is_dir():
        data_args.append(f"--add-data={docs_dir}{os.pathsep}docs")

    cmd = [
        sys.executable or "python",
        "-m", "PyInstaller",
        "--name=unframed",
        "--onefile",                # Single executable
        "--console",                # Console window
        "--clean",
        "--noconfirm",
        # Add ai-util as a hidden import (git dependency)
        "--hidden-import=ai_util",
        "--hidden-import=ai_util.bot",
        "--hidden-import=ai_util.agent",
        "--hidden-import=ai_util.tools",
        "--hidden-import=ai_util.sandbox",
        # Textual hidden imports
        "--hidden-import=textual",
        "--hidden-import=textual.app",
        "--hidden-import=textual.screen",
        "--hidden-import=textual.widgets",
        "--hidden-import=textual.containers",
        "--hidden-import=textual.keys",
        # Rich hidden imports
        "--hidden-import=rich.markdown",
        "--hidden-import=rich.console",
        "--hidden-import=rich.panel",
        "--hidden-import=rich.text",
        # Colorama
        "--hidden-import=colorama",
        # OpenAI
        "--hidden-import=openai",
        *data_args,
        str(ROOT / "src" / "unframed" / "__init__.py"),
    ]

    print("Running PyInstaller...")
    print(" ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

    print(f"\nDone! Executable at: {DIST / 'unframed'}{'.exe' if sys.platform == 'win32' else ''}")
    print("Note: seeds/ and docs/ are bundled inside the executable.")


if __name__ == "__main__":
    main()
