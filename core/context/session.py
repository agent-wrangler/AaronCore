import sys as _sys

from context import session as _impl

_sys.modules[__name__] = _impl
