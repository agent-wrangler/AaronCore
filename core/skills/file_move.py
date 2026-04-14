import sys as _sys

from tools.agent import file_move as _impl

_sys.modules[__name__] = _impl
