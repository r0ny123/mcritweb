init:
	pip install -r requirements.txt
# ruff is not in requirements.txt - CI installs it pinned, see .github/workflows/test.yml
lint:
	python3 -m ruff check .
# pytest is not in requirements.txt - it stopped arriving with mcrit in 1.8, so install
# it alongside ruff (pytest-cov for the coverage target), as CI does
test:
	python3 -m pytest
test-coverage:
	python3 -m pytest --cov=mcritweb --cov-report=html:coverage-html
clean:
	find . | grep -E "(__pycache__|\.pyc|\.pyo$\)" | xargs rm -rf
	rm -rf .coverage
	rm -rf coverage-html
	rm -rf dist/*
