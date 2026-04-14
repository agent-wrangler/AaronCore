import sys as _sys

from tools.agent import screen_capture as _impl

_sys.modules[__name__] = _impl
