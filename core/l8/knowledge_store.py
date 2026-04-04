"""Legacy compatibility shim for memory.l8.knowledge_store."""

from memory.l8 import knowledge_store as _impl
import sys


sys.modules[__name__] = _impl
