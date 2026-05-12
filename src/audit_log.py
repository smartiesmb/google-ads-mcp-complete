"""Append-only audit log for every MCP mutation.

Writes one JSON line per call to {project_root}/audit.log.
Path override: GADS_MCP_AUDIT_LOG environment variable.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict


_LOG_PATH = Path(
    os.getenv("GADS_MCP_AUDIT_LOG", str(Path(__file__).resolve().parent.parent / "audit.log"))
)


def append(entry: Dict[str, Any]) -> None:
    """Append a JSON line to the audit log. Never raises (audit must be best-effort)."""
    entry = dict(entry)
    entry.setdefault("ts", time.time())
    entry.setdefault("ts_iso", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    try:
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
    except Exception:
        pass


def path() -> Path:
    return _LOG_PATH
