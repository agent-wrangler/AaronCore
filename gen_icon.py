"""Compatibility shim for the legacy root icon script."""

from tools.desktop.gen_icon import *  # noqa: F401,F403


if __name__ == "__main__":
    from tools.desktop.gen_icon import main

    main()
