"""Compatibility shim for MCP client helpers."""

import sys as _sys

from core.mcp import client as _impl

_sys.modules[__name__] = _impl
