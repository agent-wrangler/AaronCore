"""Compatibility shim for target protocol helpers."""

import sys as _sys

from core.protocols import target as _impl

_sys.modules[__name__] = _impl
