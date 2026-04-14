import sys as _sys

from skills.builtin import content_task as _impl

_sys.modules[__name__] = _impl
