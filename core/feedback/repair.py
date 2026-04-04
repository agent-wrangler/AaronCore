import sys as _sys

from feedback import repair as _impl

_sys.modules[__name__] = _impl
