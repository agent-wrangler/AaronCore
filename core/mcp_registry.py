"""Compatibility shim for MCP registry helpers."""

import sys as _sys

from core.mcp import registry as _impl

_sys.modules[__name__] = _impl
