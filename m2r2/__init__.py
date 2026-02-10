from importlib.metadata import version

from .m2r2 import M2R2, convert

__version__ = version(__name__)

__all__ = ("M2R2", "convert", "setup")


def setup(app):
    """Sphinx extension setup function.

    This function is called by Sphinx when m2r2 is used as an extension.
    It delegates to the actual setup in m2r2.sphinx.m2r2.
    """
    from .sphinx.m2r2 import setup as sphinx_setup

    return sphinx_setup(app)
