"""Sphinx configuration for the x12sdk documentation site."""

import x12sdk

project = "x12sdk"
author = "owgreen-dev and the x12sdk contributors"
copyright = (
    "2026, owgreen-dev and contributors; original work © IBM (LinuxForHealth x12)"
)
release = x12sdk.__version__
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

source_suffix = {".md": "markdown"}
root_doc = "index"
exclude_patterns = ["_build"]

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_default_options = {"members": True, "undoc-members": False}

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# The guides cover what each module is for; module docstrings are written
# for help() and the source, not as reStructuredText, so they are left out.
# The generated transaction models are not documented class by class.
nitpick_ignore_regex = [("py:class", r"x12sdk\.(models|v5010|v4010)\..*")]


def _skip_module_docstrings(app, what, name, obj, options, lines):
    if what == "module":
        lines.clear()


def setup(app):
    app.connect("autodoc-process-docstring", _skip_module_docstrings)


html_theme = "furo"
html_title = f"x12sdk {release}"
html_baseurl = "https://owgreen-dev.github.io/x12sdk/"
html_theme_options = {
    "source_repository": "https://github.com/owgreen-dev/x12sdk/",
    "source_branch": "main",
    "source_directory": "docs/",
    "announcement": (
        '<a href="https://huggingface.co/spaces/owgreen-dev/x12sdk-playground">'
        "Try x12sdk in your browser</a>: check a file, get a CSV, or generate "
        "samples, with nothing to install."
    ),
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/owgreen-dev/x12sdk",
            "html": "GitHub",
            "class": "",
        }
    ],
}
html_static_path = []
