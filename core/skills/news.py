import sys as _sys

from skills.builtin import news as _impl

_sys.modules[__name__] = _impl
