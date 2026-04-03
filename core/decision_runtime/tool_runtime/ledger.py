"""Compatibility shim for extracted decision-domain tool ledger."""

import sys as _sys

from decision.tool_runtime import ledger as _impl

_sys.modules[__name__] = _impl

