#!/usr/bin/env python

from setuptools import setup


setup(name             = 'confit',
      version          = '0.0.0',
      install_requires = [],
      description      = 'An object-oriented DSL for system automation',
      maintainer       = 'Jason Dusek',
      maintainer_email = 'jason.dusek@gmail.com',
      url              = 'https://github.com/solidsnack/confit',
      packages         = ['confit'],
      classifiers      = ['Environment :: Console',
                          'Intended Audience :: Developers',
                          'Operating System :: Unix',
                          'Operating System :: POSIX',
                          'Programming Language :: Python',
                          'Topic :: System',
                          'Topic :: System :: Systems Administration',
                          'Topic :: Software Development',
                          'Development Status :: 4 - Beta'])
