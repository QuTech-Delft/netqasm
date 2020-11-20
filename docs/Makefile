# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SOURCEDIR     = .
BUILDDIR      = build
PYTHON3       = python3
# TODO handle like this?
export NETQASM_SIMULATOR = debug

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)


python-deps:
	@${PYTHON3} -m pip install -r requirements.txt

build: python-deps html

open:
ifeq (, $(shell which open))
	xdg-open ${BUILDDIR}/html/index.html
else
	open ${BUILDDIR}/html/index.html
endif

see: html open

.PHONY: help Makefile python-deps build open see
