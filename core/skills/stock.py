import sys as _sys

from skills.builtin import stock as _impl

_sys.modules[__name__] = _impl
