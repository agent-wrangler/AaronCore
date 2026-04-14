"""Compatibility shim for decision runtime verification helpers."""

import sys as _sys

from core.decision_runtime import nerve as _impl

_sys.modules[__name__] = _impl
