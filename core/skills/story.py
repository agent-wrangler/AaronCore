import sys as _sys

from skills.builtin import story as _impl

_sys.modules[__name__] = _impl
