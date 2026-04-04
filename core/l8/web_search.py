"""Legacy compatibility shim for memory.l8.web_search."""

from memory.l8 import web_search as _impl
import sys


sys.modules[__name__] = _impl
