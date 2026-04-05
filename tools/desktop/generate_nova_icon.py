"""Compatibility shim for legacy Nova icon entrypoints."""

from tools.desktop.generate_aaroncore_icon import *  # noqa: F401,F403


if __name__ == "__main__":
    from tools.desktop.generate_aaroncore_icon import main

    main()
