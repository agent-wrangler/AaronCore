"""Compatibility shim for extracted decision-domain tool events."""

import sys as _sys

from decision.tool_runtime import events as _impl

_sys.modules[__name__] = _impl

