import sys as _sys

from tools.agent import app_target as _impl

_sys.modules[__name__] = _impl
