"""Compatibility shim for event-bus helpers."""

import sys as _sys

from core.context import events as _impl

_sys.modules[__name__] = _impl
