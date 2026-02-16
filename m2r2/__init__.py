from importlib.metadata import version

from .m2r2 import M2R2, convert

__version__ = version(__name__)

from .sphinx.m2r2 import setup

__all__ = ("M2R2", "convert", "setup")
