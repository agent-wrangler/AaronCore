"""Compatibility shim for vision protocol helpers."""

import sys as _sys

from core.protocols import vision as _impl

_sys.modules[__name__] = _impl
