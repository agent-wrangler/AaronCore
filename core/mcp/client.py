import sys as _sys

from mcp_integration import client as _impl

_sys.modules[__name__] = _impl
