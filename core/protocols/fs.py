import sys as _sys

from protocols import fs as _impl

_sys.modules[__name__] = _impl
