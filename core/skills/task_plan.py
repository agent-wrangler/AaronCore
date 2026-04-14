import sys as _sys

from skills.builtin import task_plan as _impl

_sys.modules[__name__] = _impl
