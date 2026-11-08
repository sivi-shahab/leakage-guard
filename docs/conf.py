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

html_theme = "pydata_sphinx_theme"
html_title = "leakage-guard"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_context = {
    "github_user": "sivi-shahab",
    "github_repo": "leakage-guard",
    "github_version": "main",
    "doc_path": "data-leakage/leakage-guard/docs",
}
html_theme_options = {
    "github_url": "https://github.com/sivi-shahab/leakage-guard",
    "navbar_align": "left",
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
    "header_links_before_dropdown": 6,
    "show_toc_level": 2,
    "navigation_with_keys": False,
    "use_edit_page_button": True,
    "secondary_sidebar_items": ["page-toc", "edit-this-page"],
    "footer_start": ["copyright"],
    "footer_end": ["sphinx-version"],
}
html_sidebars = {"index": [], "**": ["sidebar-nav-bs"]}
