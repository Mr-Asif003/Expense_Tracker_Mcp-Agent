"""Logging setup. Logs always go to **stderr**.

The MCP STDIO transport uses stdout for protocol frames, so writing anything
else to stdout from the server process would corrupt the session.
"""

from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once; safe to call repeatedly."""
    root = logging.getLogger()
    if getattr(root, "_expense_tracker_configured", False):
        root.setLevel(level.upper())
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)
    root.setLevel(level.upper())
    root._expense_tracker_configured = True  # type: ignore[attr-defined]
