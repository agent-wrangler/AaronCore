"""Compatibility shim for extracted decision-domain router helpers."""

import sys as _sys

from decision.routing import router as _impl

_sys.modules[__name__] = _impl

