"""Compatibility shim for context builder helpers."""

import sys as _sys

from core.context import builder as _impl

_sys.modules[__name__] = _impl
