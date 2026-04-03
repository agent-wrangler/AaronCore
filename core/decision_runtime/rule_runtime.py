"""Compatibility shim for extracted decision-domain rule evaluation."""

import sys as _sys

from decision import rule_runtime as _impl

_sys.modules[__name__] = _impl

