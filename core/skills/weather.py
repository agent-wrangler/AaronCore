import sys as _sys

from skills.builtin import weather as _impl

_sys.modules[__name__] = _impl
