"""Compatibility shim for feedback loop helpers."""

import sys as _sys

from core.feedback import loop as _impl

_sys.modules[__name__] = _impl
