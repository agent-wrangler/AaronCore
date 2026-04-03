"""Compatibility shim for decision-domain reply formatting."""

import sys as _sys

from decision import reply_formatter as _impl

_sys.modules[__name__] = _impl
