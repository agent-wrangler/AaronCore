import sys as _sys

from feedback import classifier as _impl

_sys.modules[__name__] = _impl
