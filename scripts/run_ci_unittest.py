import sys
import unittest
import os
from pathlib import Path


SUITES = {
    "smoke": [
        "test_chat_run_helpers.py",
        "test_task_continuity.py",
        "test_memory_tool_runtime.py",
        "test_desktop_shell_paths.py",
    ],
    "extended": [
        "test_model_runtime.py",
        "test_chat_image_bridge.py",
        "test_tool_call_runtime.py",
        "test_frontend_image_upload_bridge.py",
    ],
}

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in SUITES:
        valid = ", ".join(sorted(SUITES))
        print(f"Usage: python scripts/run_ci_unittest.py <{valid}>", file=sys.stderr)
        return 2

    suite_name = argv[1]
    root_str = str(ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    os.chdir(ROOT)

    suite = unittest.TestSuite()
    for pattern in SUITES[suite_name]:
        loader = unittest.TestLoader()
        suite.addTests(loader.discover("tests", pattern=pattern))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
