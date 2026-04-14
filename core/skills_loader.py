import sys as _sys

from capability_registry import loader as _impl

_sys.modules[__name__] = _impl
