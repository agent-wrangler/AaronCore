"""Legacy compatibility shim for memory.l8.quality_guard."""

from memory.l8 import quality_guard as _impl
import sys


sys.modules[__name__] = _impl
