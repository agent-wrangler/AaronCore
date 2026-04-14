"""Compatibility shim for self-repair helpers."""

import sys as _sys

from core.feedback import repair as _impl

_sys.modules[__name__] = _impl
