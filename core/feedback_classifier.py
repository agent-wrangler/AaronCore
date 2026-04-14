"""Compatibility shim for feedback classifier helpers."""

import sys as _sys

from core.feedback import classifier as _impl

_sys.modules[__name__] = _impl
