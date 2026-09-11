"""Compatibility entry point; only the forward PAPER service is available."""
from trading_backend.forward.service import main

if __name__ == "__main__":
    raise SystemExit(main())
