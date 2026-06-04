from importlib import import_module

_IO_EXPORTS = {"tle_ingestor", "TLEIngestor"}


def __getattr__(name: str):
    if name not in _IO_EXPORTS:
        raise AttributeError(f"module 'engine.io' has no attribute {name!r}")
    module = import_module(".data", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
