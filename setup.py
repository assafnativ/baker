#!python

from setuptools import setup

setup(name="Baker",
      version="1.02",
      py_modules=["baker"],
      
      author="Matt Chaput",
      author_email="matt@whoosh.ca",
      
      description="Easy, powerful access to Python functions from the command line",
      long_description = open("README.txt").read(),
      
      license="Apache 2.0",
      keywords="command line scripting",
      url="http://bitbucket.org/mchaput/baker",
      
      classifiers = ["Development Status :: 4 - Beta",
                     "Intended Audience :: Developers",
                     "Intended Audience :: System Administrators",
                     "Environment :: Console",
                     "License :: OSI Approved :: Apache Software License",
                     "Operating System :: OS Independent",
                     "Programming Language :: Python",
                     ]
      )
