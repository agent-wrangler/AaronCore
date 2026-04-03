"""Compatibility shim for extracted decision-domain batch tool runtime."""

import sys as _sys

from decision.tool_runtime import batch as _impl

_sys.modules[__name__] = _impl

