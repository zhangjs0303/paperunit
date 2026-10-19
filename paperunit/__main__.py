"""Allow ``python3 -m paperunit`` from a checkout."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
