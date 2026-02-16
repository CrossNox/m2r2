from importlib.metadata import version

from .m2r2 import M2R2, convert

__version__ = version(__name__)

# Imported after __version__ is set to avoid circular import:
# sphinx.m2r2 -> m2r2.__version__ must already exist.
from .sphinx.m2r2 import setup

__all__ = ("M2R2", "convert", "setup")
