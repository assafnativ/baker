.PHONY: tox tests cov htmlcov check-deps tox-deps cov-deps tests-deps clean

all: tox-deps tox

tox:
	tox

tests:
	cd tests
	nosetests --with-specplugin

cov:
	coverage run tests/test_baker.py

htmlcov:
	coverage html

check-deps: tox-deps cov-deps tests-deps

tox-deps:
	pip install tox

cov-deps:
	pip install coverage

tests-deps:
	pip install nose spec

clean:
	rm -r build/
	rm -r Baker.egg-info/
	rm -r htmlcov/
