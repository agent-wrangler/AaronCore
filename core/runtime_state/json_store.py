import sys as _sys

from storage import json_store as _impl

_sys.modules[__name__] = _impl
