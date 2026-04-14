"""Compatibility shim for decision runtime reply formatting."""

import sys as _sys

from core.decision_runtime import reply_formatter as _impl

_sys.modules[__name__] = _impl
