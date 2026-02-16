from importlib.metadata import version

from .m2r2 import M2R2, convert
from .sphinx.m2r2 import setup

__version__ = version(__name__)
__all__ = ("M2R2", "convert", "setup")
