"""Build a standalone .exe using PyInstaller."""

import subprocess
import sys

def main() -> None:
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "BibMergeTool",
        "--add-data", f"bibtool{sep}bibtool",
        "gui.py",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("\nDone. exe is in dist/BibMergeTool.exe")

if __name__ == "__main__":
    main()
