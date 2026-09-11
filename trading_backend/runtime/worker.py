"""Retired runtime. Use trading_backend.forward; historical storage is untouched."""

class RuntimeWorker:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Legacy trading runtime disabled; use the forward paper service")
