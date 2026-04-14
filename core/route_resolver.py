"""Compatibility shim for decision runtime route resolution."""

import sys as _sys

from core.decision_runtime import route_resolver as _impl

_sys.modules[__name__] = _impl
