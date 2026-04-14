import sys as _sys

from tools.agent import folder_explore as _impl

_sys.modules[__name__] = _impl
