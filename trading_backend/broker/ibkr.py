"""Retired runtime. Use trading_backend.forward; historical storage is untouched."""

class IBKRBrokerAdapter:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Legacy trading runtime disabled; use the forward paper service")

class MockBrokerAdapter:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Legacy trading runtime disabled; use the forward paper service")
