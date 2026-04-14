import sys as _sys

from skills.builtin import article as _impl

_sys.modules[__name__] = _impl
