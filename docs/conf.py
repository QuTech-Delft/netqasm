# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = "netqasm"
copyright = "2021, QuTech"
author = "QuTech"

# The full version, including alpha/beta/rc tags
release = "0.9.0"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.githubpages",
    "sphinx.ext.todo",
    "sphinx.ext.mathjax",
    "sphinx.ext.intersphinx",
    "sphinx.ext.doctest",
    "sphinx.ext.extlinks",
    "sphinx_autodoc_typehints",
    # 'sphinx_exercise',
]
napoleon_include_init_with_doc = True
autodoc_member_order = "bysource"
# autoclass_content = 'both'
always_document_param_types = True

# set_type_checking_flag = True

extlinks = {
    "netsquid": ("https://netsquid.org/%s", ""),
    "simulaqron": ("http://www.simulaqron.org/%s", ""),
    "squidasm": ("https://github.com/QuTech-Delft/squidasm/%s", ""),
    "network-layer": ("https://arxiv.org/abs/2010.02575/%s", ""),
    "repcode": ("https://en.wikipedia.org/wiki/Quantum_error_correction/%s", ""),
    "netqasm-paper": (
        "https://gitlab.tudelft.nl/qinc-wehner/netqasm/netqasm-paper/%s",
        "",
    ),
    # TODO add link to qnodeos
    "qnodeos": ("%s", ""),
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
