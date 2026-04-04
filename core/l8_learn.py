"""Legacy compatibility shim for the memory-domain L8 learning module."""

from memory import l8_learning as _impl
import sys


sys.modules[__name__] = _impl
