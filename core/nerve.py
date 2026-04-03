"""Compatibility shim for decision-domain verification helpers."""

import sys as _sys

from decision.routing import nerve as _impl

_sys.modules[__name__] = _impl
