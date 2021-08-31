test:
	poetry run pytest -s -rf -vv --log-level=debug --cov-config=.coveragerc --cov cats tests
	poetry run python -m coverage xml -i
	poetry run python -m coverage html -i
	poetry run python -m coverage report > coverage.txt

publish:
	poetry publish --build