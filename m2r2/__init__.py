from .m2r2 import M2R2, convert

try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:
    import importlib_metadata  # type: ignore

__version__ = importlib_metadata.version(__name__)  # type: ignore

__all__ = ("M2R2", "convert")
