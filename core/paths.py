"""
Locates the application's resources/ folder in every way the program can run:
from source, as a Nuitka onefile/standalone executable (data embedded or placed
next to the .exe), or as a PyInstaller bundle.
"""

import os
import sys

_resources_dir = None


def _candidates():
    """
    Returns: list of str - possible base directories that may contain resources/
    """
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = [os.path.dirname(here)]                              # source tree / onefile temp
    if "__compiled__" in globals():                             # Nuitka
        dirs.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    dirs.append(os.path.dirname(os.path.abspath(sys.executable)))  # next to the .exe
    dirs.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    if hasattr(sys, "_MEIPASS"):                                # PyInstaller
        dirs.append(sys._MEIPASS)
    dirs.append(os.getcwd())
    out = []
    for d in dirs:
        if d not in out:
            out.append(d)
    return out


def resources_dir():
    """
    Returns: str or None - absolute path of the resources/ folder, or None if not found
    """
    global _resources_dir
    if _resources_dir is None:
        for base in _candidates():
            path = os.path.join(base, "resources")
            if os.path.isdir(path):
                _resources_dir = path
                break
    return _resources_dir


def resource_path(*parts):
    """
    Builds a path inside resources/.

    Args:
        *parts: str - path components below resources/ (e.g. "tnc_commands", "x.json")

    Returns: str or None - full path, or None if resources/ was not found
    """
    base = resources_dir()
    return os.path.join(base, *parts) if base else None
