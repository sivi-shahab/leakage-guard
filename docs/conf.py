"""Sphinx configuration for the leakage-guard documentation."""

project = "leakage-guard"
author = "leakage-guard contributors"
copyright = "2026, leakage-guard contributors"  # noqa: A001

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinx_design",
]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
master_doc = "index"
# Indonesian project documents stay readable on GitHub but are not part of the English site.
exclude_patterns = ["_build", "USAGE.md", "MILESTONE-*.md", "spec-verification.md", "architecture-diagram*"]
myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3
suppress_warnings = ["myst.header"]

autodoc_member_order = "bysource"
autodoc_typehints = "description"
napoleon_google_docstring = True
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
    "sklearn": ("https://scikit-learn.org/stable", None),
}

html_theme = "furo"
html_title = "leakage-guard"
html_static_path = ["_static"]
html_theme_options = {
    "source_repository": "https://github.com/OWNER/REPO/",  # TODO(owner): set the real repository
    "source_branch": "main",
    "source_directory": "leakage-guard/docs/",
    "light_css_variables": {"color-brand-primary": "#2b5fd9", "color-brand-content": "#2b5fd9"},
    "dark_css_variables": {"color-brand-primary": "#7aa2ff", "color-brand-content": "#7aa2ff"},
}
