import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path


_IMPL_PATH = _Path(__file__).resolve().parents[2] / "skills" / "builtin" / "news.py"
_SPEC = _importlib_util.spec_from_file_location("aaroncore_builtin_news", _IMPL_PATH)
_MODULE = _importlib_util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_MODULE)
_sys.modules[__name__] = _MODULE
