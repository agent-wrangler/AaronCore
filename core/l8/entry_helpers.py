"""Legacy compatibility shim for memory.l8.entry_helpers."""

from memory.l8 import entry_helpers as _impl
import sys


sys.modules[__name__] = _impl
