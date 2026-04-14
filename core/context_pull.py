"""Compatibility shim for context pull helpers."""

import sys as _sys

from core.context import pull as _impl

_sys.modules[__name__] = _impl
