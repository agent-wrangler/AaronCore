"""Compatibility shim for network protocol helpers."""

import sys as _sys

from core.protocols import network as _impl

_sys.modules[__name__] = _impl
