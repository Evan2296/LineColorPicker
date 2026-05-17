#!/usr/bin/env python3
"""
color_tracer.py — Entry point for the Color Tracer application.

Run:
    python3 color_tracer.py

A file browser will open so you can choose an image.
If the current Python lacks tkinter, the script automatically
re-launches itself with a compatible interpreter.

Controls:
    Left click   — add a point to your trace path
    Right click  — undo the last point
    Enter        — sample all unique colors along the path
    R            — reset all points and start over
    Q / Escape   — quit
"""

import sys
import os
import subprocess


def _ensure_tkinter():
    """
    Verify tkinter is importable; if not, find a Homebrew Python that has it
    and re-exec this script under that interpreter.

    Exits with an error message if no compatible Python is found.
    """
    try:
        import tkinter  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    candidates = [
        "/opt/homebrew/bin/python3.11",
        "/opt/homebrew/bin/python3.12",
        "/opt/homebrew/bin/python3.10",
        "/opt/homebrew/bin/python3",
        "/usr/bin/python3",
    ]

    for py in candidates:
        if not os.path.exists(py):
            continue
        result = subprocess.run([py, "-c", "import tkinter"], capture_output=True)
        if result.returncode == 0:
            print(f"[color_tracer] Re-launching with {py} (has tkinter)...")
            os.execv(py, [py] + sys.argv)

    print(
        "\nERROR: Could not find a Python with tkinter.\n"
        "Fix:   brew install python-tk@3.11\n"
        "Then run this script again.\n"
    )
    sys.exit(1)


# Run the tkinter check before any other local imports so the error
# surfaces early and clearly on systems without tkinter support.
_ensure_tkinter()

from app import main  # noqa: E402  (import after runtime check)

if __name__ == "__main__":
    main()
