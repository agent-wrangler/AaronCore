import sys as _sys

from core.task_runtime import store as _impl

_sys.modules[__name__] = _impl
