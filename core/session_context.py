"""Compatibility shim for session context helpers."""

import sys as _sys

from core.context import session as _impl

_sys.modules[__name__] = _impl
