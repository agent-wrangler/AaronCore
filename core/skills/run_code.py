import sys as _sys

from tools.agent import run_code as _impl

_sys.modules[__name__] = _impl
