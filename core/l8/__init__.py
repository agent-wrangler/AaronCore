"""Legacy compatibility package for memory.l8."""

from memory import l8 as _impl
import sys


sys.modules[__name__] = _impl
