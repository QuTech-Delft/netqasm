PYTHON3              = python3
SOURCEDIR            = netqasm
TESTDIR              = tests
EXAMPLEDIR           = netqasm/examples
EXTERNAL_PIP_FLAGS   = --extra-index-url=https://${NETSQUIDPYPI_USER}:${NETSQUIDPYPI_PWD}@pypi.netsquid.org
RUNEXAMPLES          = ${EXAMPLEDIR}/run_examples.py
MINCOV               = 0
EXT_TEST             = test_external

help:
	@echo "install           Installs the package (editable)."
	@echo "verify            Verifies the installation, runs the linter and tests."
	@echo "tests             Runs the tests."
	@echo "external-tests    Runs the external tests (downstream dependencies)."
	@echo "examples          Runs the examples and makes sure they work."
	@echo "open-cov-report   Creates and opens the coverage report."
	@echo "lint              Runs the linter."
	@echo "bdist             Builds the package."
	@echo "test-deps         Installs the requirements needed for running tests and linter."
	@echo "external-test-deps Installs the requirements needed for running external tests."
	@echo "python-deps       Installs the requirements needed for using the package."
	@echo "docs              Creates the html documentation"
	@echo "clean             Removes all .pyc files."

test-deps:
	@$(PYTHON3) -m pip install -r test_requirements.txt

external-test-deps:
	@$(PYTHON3) -m pip install -r external_test_requirements.txt ${EXTERNAL_PIP_FLAGS}

requirements python-deps:
	@$(PYTHON3) -m pip install -r requirements.txt

clean:
	@/usr/bin/find . -name '*.pyc' -delete

lint:
	@$(PYTHON3) -m flake8 ${SOURCEDIR} ${TESTDIR}
	@$(PYTHON3) -m mypy ${SOURCEDIR} ${TESTDIR}

tests:
	@$(PYTHON3) -m pytest --cov=${SOURCEDIR} --cov-fail-under=${MINCOV} --ignore=${TESTDIR}/${EXT_TEST} ${TESTDIR}

external-tests:
	@$(PYTHON3) -m pytest tests/test_external

open-cov-report:
	@$(PYTHON3) -m pytest --cov=${SOURCEDIR} --cov-report html ${TESTDIR} && open htmlcov/index.html

examples:
	@${PYTHON3} ${RUNEXAMPLES}

external-examples:
	@${PYTHON3} ${RUNEXAMPLES} --external

docs html:
	@${MAKE} -C docs html

build bdist: _clean_dist
	@$(PYTHON3) setup.py bdist_wheel

install: test-deps
	@$(PYTHON3) -m pip install -e .

_clean_dist:
	@/bin/rm -rf dist

verify: clean test-deps python-deps lint tests examples _verified

_verified:
	@echo "The snippet is verified :)"

.PHONY: clean lint test-deps python-deps tests verify bdist deploy-bdist _clean_dist install open-cov-report examples docs
