.PHONY: tests tests-deps

all: tests-deps tests

tests:
	cd tests
	nosetests --with-specplugin

tests-deps:
	pip install nose spec
