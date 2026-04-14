"""Compatibility shim for decision runtime rule evaluation."""

import sys as _sys

from core.decision_runtime import rule_runtime as _impl

_sys.modules[__name__] = _impl
