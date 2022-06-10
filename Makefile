PYTHON3              = python3
SOURCEDIR            = netqasm
TESTDIR              = tests
EXAMPLEDIR           = netqasm/examples
EXTERNAL_PIP_FLAGS   = --extra-index-url=https://${NETSQUIDPYPI_USER}:${NETSQUIDPYPI_PWD}@pypi.netsquid.org
RUNEXAMPLES          = ${EXAMPLEDIR}/run_examples.py
EXT_TEST             = test_external

help:
	@echo "install           Installs the package (editable)."
	@echo "verify            Verifies the installation, runs the linter and tests."
	@echo "tests             Runs the tests."
	@echo "external-tests    Runs the external tests (downstream dependencies)."
	@echo "examples          Runs the examples and makes sure they work."
	@echo "lint              Runs the linter."
	@echo "docs              Creates the html documentation"
	@echo "clean             Removes all .pyc files."

clean:
	@/usr/bin/find . -name '*.pyc' -delete

lint-isort:
	$(info Running isort...)
	@$(PYTHON3) -m isort --check ${SOURCEDIR} ${TESTDIR}

lint-black:
	$(info Running black...)
	@$(PYTHON3) -m black --check ${SOURCEDIR} ${TESTDIR}

lint-flake8:
	$(info Running flake8...)
	@$(PYTHON3) -m flake8 ${SOURCEDIR} ${TESTDIR}

lint-mypy:
	$(info Running mypy...)
	@$(PYTHON3) -m mypy ${SOURCEDIR} ${TESTDIR}

lint: lint-isort lint-black lint-flake8 lint-mypy

tests:
	@$(PYTHON3) -m pytest --ignore=${TESTDIR}/${EXT_TEST} ${TESTDIR}

external-tests:
	@$(PYTHON3) -m pytest tests/test_external

examples:
	@${PYTHON3} ${RUNEXAMPLES}

external-examples:
	@${PYTHON3} ${RUNEXAMPLES} --external

docs html:
	@${MAKE} -C docs html

install:
	@$(PYTHON3) -m pip install -e .

install-dev:
	@$(PYTHON3) -m pip install -e .[dev]

install-squidasm:
	@$(PYTHON3) -m pip install -e .[squidasm] ${EXTERNAL_PIP_FLAGS}

verify: clean install install-dev lint tests examples _verified

_verified:
	@echo "Everything OK!"

.PHONY: clean lint tests verify install install-dev install-squidasm examples docs
