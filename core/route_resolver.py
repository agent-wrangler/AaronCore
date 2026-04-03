"""Compatibility shim for decision-domain route resolution."""

import sys as _sys

from decision.routing import route_resolver as _impl

_sys.modules[__name__] = _impl
