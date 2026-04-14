"""Compatibility shim for decision runtime routing helpers."""

import sys as _sys

from core.decision_runtime import router as _impl

_sys.modules[__name__] = _impl
