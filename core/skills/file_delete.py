import sys as _sys

from tools.agent import file_delete as _impl

_sys.modules[__name__] = _impl
