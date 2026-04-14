"""Compatibility shim for filesystem protocol helpers."""

import sys as _sys

from core.protocols import fs as _impl

_sys.modules[__name__] = _impl
