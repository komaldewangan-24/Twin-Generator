"""Pytest configuration.

Points the app at an isolated temporary SQLite database *before* any app
module is imported, so tests never read or delete the development database
(which would also fail while `uvicorn --reload` holds the file open).
"""

import atexit
import os
import shutil
import tempfile
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="digitaltwin_tests_")
_DB_FILE = Path(_TMP_DIR) / "test.db"

os.environ["DATABASE_URL"] = f"sqlite:///{_DB_FILE.as_posix()}"

atexit.register(shutil.rmtree, _TMP_DIR, ignore_errors=True)