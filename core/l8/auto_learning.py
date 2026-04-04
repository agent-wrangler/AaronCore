"""Legacy compatibility shim for memory.l8.auto_learning."""

from memory.l8 import auto_learning as _impl
import sys


sys.modules[__name__] = _impl
