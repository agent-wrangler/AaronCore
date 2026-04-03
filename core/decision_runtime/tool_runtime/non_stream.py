"""Compatibility shim for extracted decision-domain non-stream tool runtime."""

import sys as _sys

from decision.tool_runtime import non_stream as _impl

_sys.modules[__name__] = _impl

