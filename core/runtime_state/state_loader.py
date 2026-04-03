import sys as _sys

from storage import state_loader as _impl

_sys.modules[__name__] = _impl
