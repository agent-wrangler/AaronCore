import sys as _sys

from tools.agent import draw as _impl

_sys.modules[__name__] = _impl
