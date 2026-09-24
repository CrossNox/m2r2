import warnings

from m2r2.m2r2 import __version__
from m2r2.sphinx.directives import MdInclude


def validate_sphinx_config(app):
    """Validate converter settings and warn about deprecated Sphinx options."""
    if app.config.no_underscore_emphasis:
        warnings.warn(
            "The 'no_underscore_emphasis' config value is deprecated. "
            "Use 'm2r_no_underscore_emphasis' instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    from sphinx.errors import ConfigError
    from sphinx.util import logging

    if app.config.m2r_disable_inline_math is not None:
        logging.getLogger(__name__).warning(
            "m2r_disable_inline_math is deprecated. Use m2r_inline_math = None "
            "to disable inline math, or 'legacy' to retain legacy syntax. "
            "An explicit m2r_inline_math setting takes precedence.",
            type="m2r2",
            subtype="deprecated",
        )
    inline_math = app.config.m2r_inline_math
    if inline_math not in ("legacy", "dollar", None):
        raise ConfigError(
            f"m2r_inline_math must be 'legacy', 'dollar', or None, got {inline_math!r}"
        )


def resolve_deprecated_inline_math(disable_inline_math):
    """Translate the deprecated Sphinx setting into an inline math mode."""
    from sphinx.errors import ConfigError

    # Sphinx 1.7 leaves -D overrides as strings when the default is None.
    if disable_inline_math in (None, False, "0"):
        return "legacy"
    if disable_inline_math in (True, "1"):
        return None
    raise ConfigError(
        "m2r_disable_inline_math must be a boolean or a 0/1 override, "
        f"got {disable_inline_math!r}"
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
    app.add_config_value(
        "m2r_disable_inline_math", None, "env", [bool, str, type(None)]
    )
    app.add_config_value(
        "m2r_inline_math",
        lambda config: resolve_deprecated_inline_math(config.m2r_disable_inline_math),
        "env",
        [str, type(None)],
    )
    app.add_config_value(
        "m2r_use_mermaid",
        "sphinxcontrib.mermaid" in app.config.extensions,
        "env",
    )
    app.connect("builder-inited", validate_sphinx_config)
    app.add_directive("mdinclude", MdInclude)
    register_document_anchors(app)
    return {
        "version": __version__,
        "env_version": 1,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
