test:
	poetry run python -m coverage run || exit $?
	poetry run python -m coverage report
	poetry run python -m coverage html -i

test-debug:
	poetry run pytest -s -rf -vv -x --log-level=debug tests

publish:
	poetry publish --build