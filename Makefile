VENV_NAME?=pe38
VENV_ACTIVATE=. ~/$(VENV_NAME)/bin/activate
PYTHON=~/${VENV_NAME}/bin/python3
PIP = pip3
PYCOV = $(PYTHON) -m coverage
PYTEST = tests
SRC = IGaten

.DEFAULT_GOAL := fullcheck
fullcheck:
	$(MAKE) check
	$(MAKE) test


check:
	$(PYTHON) -m black --check --diff $(SRC)
#	$(PYTHON) -m pylint -E            $(SRC)

coverage:
	$(PYCOV) erase
	$(RM)  coverage.txt
	-$(PYCOV) run -a -m pytest
	$(PYCOV) report  --include=$(SRC)/* > ./coverage.txt
	cat ./coverage.txt

.PHONY: doc
doc:
	$(VENV_ACTIVATE) && cd Doc; make html

.PHONY: docserve
docserve: doc
	$(VENV_ACTIVATE) && cd Doc/build/html; echo "Press Ctrl C to stop " && $(PYTHON) -m http.server  

format:
	$(PYTHON) -m black $(SRC)
	$(PYTHON) -m black $(PYTEST)

test:
	$(PYTHON) -m pytest $(PYTEST)

