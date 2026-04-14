"""Compatibility shim for the desktop icon generator."""

from tools.desktop.generate_nova_icon import *  # noqa: F401,F403


if __name__ == "__main__":
    from tools.desktop.generate_nova_icon import main

    main()
