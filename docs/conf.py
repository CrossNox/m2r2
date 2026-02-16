from m2r2 import __version__ as __m2r2_version__

# -- General configuration ------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.mathjax",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
    "m2r2",
]

suppress_warnings = ["image.nonlocal_uri"]
templates_path = ["_templates"]
source_suffix = ".md"
master_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- m2r2 configuration --------------------------------------------------

m2r_no_underscore_emphasis = True
m2r_parse_relative_links = True
m2r_anonymous_references = False
m2r_disable_inline_math = False

# -- Project information --------------------------------------------------

project = "M2R2"
copyright = "2025, CrossNox"
author = "CrossNox"
version = __m2r2_version__
release = __m2r2_version__
language = "en"

# -- Options for HTML output ----------------------------------------------

html_theme = "alabaster"
html_theme_options = {
    "description": "Markdown mixed to reST",
    "github_user": "CrossNox",
    "github_repo": "m2r2",
    "github_banner": True,
    "github_type": "mark",
    "github_count": False,
    "font_family": '"Charis SIL", "Noto Serif", serif',
    "head_font_family": "Lato, sans-serif",
    "code_font_family": '"Code new roman", "Ubuntu Mono", monospace',
    "code_font_size": "1rem",
}
html_static_path = ["_static"]
html_sidebars = {
    "**": [
        "about.html",
        "navigation.html",
        "relations.html",
        "searchbox.html",
    ]
}
htmlhelp_basename = "M2Rdoc"
pygments_style = "sphinx"
