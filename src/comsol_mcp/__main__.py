"""Allow launching via `python -m comsol_mcp`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
