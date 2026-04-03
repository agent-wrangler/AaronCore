"""Compatibility shim for extracted decision-domain stream tool runtime."""

import sys as _sys

from decision.tool_runtime import stream as _impl

_sys.modules[__name__] = _impl
