"""Legacy compatibility shim for memory.l8.feedback_learning."""

from memory.l8 import feedback_learning as _impl
import sys


sys.modules[__name__] = _impl
