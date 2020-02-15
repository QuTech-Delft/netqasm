PYTHON3        = python3
SOURCEDIR      = netqasm
TESTS_DIR      = tests
EXAMPLES_DIR   = examples
RUNEXAMPLES    = ${EXAMPLES_DIR}/run_examples.py
MINCOV         = 0

help:
	@echo "install           Installs the package (editable)."
	@echo "verify            Verifies the installation, runs the linter and tests."
	@echo "tests             Runs the tests."
	@echo "examples          Runs the examples and makes sure they work."
	@echo "open-cov-report   Creates and opens the coverage report."
	@echo "lint              Runs the linter."
	@echo "bdist             Builds the package."
	@echo "test-deps         Installs the requirements needed for running tests and linter."
	@echo "python-deps       Installs the requirements needed for using the package."
	@echo "docs              Creates the html documentation"
	@echo "clean             Removes all .pyc files."

test-deps:
	@$(PYTHON3) -m pip install -r test_requirements.txt

requirements python-deps:
	@$(PYTHON3) -m pip install -r requirements.txt ${PIP_FLAGS}

clean:
	@/usr/bin/find . -name '*.pyc' -delete

lint:
	@$(PYTHON3) -m flake8 ${SOURCEDIR} ${TESTDIR} ${EXAMPLEDIR}

tests:
	@$(PYTHON3) -m pytest --cov=${SOURCEDIR} --cov-fail-under=${MINCOV} tests

open-cov-report:
	@$(PYTHON3) -m pytest --cov=${SOURCEDIR} --cov-report html tests && open htmlcov/index.html

examples:
	@${PYTHON3} ${RUNEXAMPLES} > /dev/null && echo "Examples OK!" || echo "Examples failed!"

docs html:
	@${MAKE} -C docs html

build bdist: _clean_dist
	@$(PYTHON3) setup.py bdist_wheel

install: test-deps
	@$(PYTHON3) -m pip install -e . ${PIP_FLAGS}

_clean_dist:
	@/bin/rm -rf dist

verify: clean test-deps python-deps lint tests examples _verified

_verified:
	@echo "The snippet is verified :)"

.PHONY: clean lint test-deps python-deps tests verify bdist deploy-bdist _clean_dist install open-cov-report examples docs
