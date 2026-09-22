import warnings

from m2r2.m2r2 import __version__
from m2r2.sphinx.directives import MdInclude


def warn_deprecated_config(app):
    """Warn when the deprecated emphasis option is enabled."""
    if app.config.no_underscore_emphasis:
        warnings.warn(
            "The 'no_underscore_emphasis' config value is deprecated. "
            "Use 'm2r_no_underscore_emphasis' instead.",
            DeprecationWarning,
            stacklevel=2,
        )


def setup(app):
    """Register m2r2 config values, mdinclude and document anchor links."""
    # m2r2 works without Sphinx installed, and m2r2/__init__.py imports this module
    from m2r2.sphinx.anchors import register_document_anchors

    # Deprecated name kept for backward compatibility
    app.add_config_value("no_underscore_emphasis", False, "env")
    app.add_config_value(
        "m2r_no_underscore_emphasis",
        lambda config: config.no_underscore_emphasis,
        "env",
    )
    app.add_config_value("m2r_parse_relative_links", False, "env")
    app.add_config_value("m2r_anonymous_references", False, "env")
    app.add_config_value("m2r_disable_inline_math", False, "env")
    app.add_config_value(
        "m2r_use_mermaid",
        "sphinxcontrib.mermaid" in app.config.extensions,
        "env",
    )
    app.connect("builder-inited", warn_deprecated_config)
    app.add_directive("mdinclude", MdInclude)
    register_document_anchors(app)
    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
