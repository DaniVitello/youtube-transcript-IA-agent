"""Logging simple con prefijo de etapa."""

from __future__ import annotations

import logging
import sys

_configured = False


def get_logger(name: str = "yt-agent") -> logging.Logger:
    global _configured
    logger = logging.getLogger(name)
    if not _configured:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        _configured = True
    return logger
