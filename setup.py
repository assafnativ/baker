#!/usr/bin/env python

from setuptools import setup
import baker

setup(name="Baker",
      version=baker.__version__,
      py_modules=["baker"],
      
      author="Matt Chaput",
      author_email="matt@whoosh.ca",
      maintainer="Michele Lacchia",
      maintainer_email="michelelacchia@gmail.com",
      
      description="Easy, powerful access to Python functions from the command line",
      long_description = open("README.txt").read(),
      
      license="Apache 2.0",
      keywords="command line scripting",
      url="http://bitbucket.org/mchaput/baker",
      
      classifiers = ["Development Status :: 5 - Production/Stable",
                     "Intended Audience :: Developers",
                     "Intended Audience :: System Administrators",
                     "Environment :: Console",
                     "License :: OSI Approved :: Apache Software License",
                     "Operating System :: OS Independent",
                     "Programming Language :: Python",
                     "Programming Language :: Python :: 2",
                     "Programming Language :: Python :: 2.6",
                     "Programming Language :: Python :: 2.7",
                     "Programming Language :: Python :: 3",
                     "Programming Language :: Python :: 3.2",
                     ]
      )
