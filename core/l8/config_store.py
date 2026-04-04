"""Legacy compatibility shim for memory.l8.config_store."""

from memory.l8 import config_store as _impl
import sys


sys.modules[__name__] = _impl
