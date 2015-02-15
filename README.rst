---------------
Getting Started
---------------

* Install

.. code-block:: bash

    pip install https://github.com/solidsnack/confit/archive/master.zip

* Write a class that subclasses ``Task``

.. code-block:: python

    from confit import cc

    class SolidsnackDots(cc.Task):
        """Install solidsnack's dotfiles."""

        def code(self):
            return """
                cd ~
                git clone https://github.com/solidsnack/dots.git
                cd dots
                make install
            """

* Call ``.script()`` to generate a Bash script, to run locally or remotely, or
  ``.run()`` to run the task directly.

.. code-block:: python

    dots = SolidsnackDots()
    dots.run()


---------------------------
Using Wrappers and Subtasks
---------------------------

Confit supports a notion of "wrappers" or "task transformers". For example,
running a task as root, or running it in a certain directory.

.. code-block:: python

    #!/usr/bin/env python

    from confit import cc


    class GitCheckout(cc.Task):
        def __init__(self, repo, target=None):
            self.repo = repo
            self.target = target

        def code(self):
            if self.target is not None:
                argv = ['git', 'clone', self.repo, self.target]
            else:
                argv = ['git', 'clone', self.repo]
            return [argv]
            # When code is arrays of arrays, all values will be automatically
            # shell escaped, using ``pipes.quote()``.


    class SolidsnackDots(cc.Task):
        def deps(self):
            url = 'https://github.com/solidsnack/dots.git'
            return [
                cc.CD('~')(
                    GitCheckout(url, 'dots'),
                    cc.CD('dots')(
                        cc.Bash([['make', 'install']])
                    )
                )
            ]


    print SolidsnackDots().script()

You should expect the generated code to be in general quite readable:

.. code-block:: bash

    #!/bin/bash
    set -o errexit -o nounset -o pipefail

    export LC_ALL=en_US.UTF-8

    function GitCheckout//4dfbe151486ae2d6 {
      [[ ${_4dfbe151486ae2d6+_} ]] && return || _4dfbe151486ae2d6=_ # only once
      git clone https://github.com/solidsnack/dots.git dots
    }

    function SolidsnackDots//5386fae40f7eb977 {
      [[ ${_5386fae40f7eb977+_} ]] && return || _5386fae40f7eb977=_ # only once
      SolidsnackDots//5386fae40f7eb977//pre
      : # Do nothing.
    }
    function SolidsnackDots//5386fae40f7eb977//pre {
      confit.CD//78108f633935aefe
    }

    function confit.Bash//1897a59a84b95fee {
      make install
    }

    function confit.CD//2f09153924b83023 {
      ( set -o errexit -o nounset -o pipefail
        cd dots
        confit.CD//2f09153924b83023//inner
      )
    }
    function confit.CD//2f09153924b83023//inner {
      confit.Bash//1897a59a84b95fee
    }

    function confit.CD//78108f633935aefe {
      ( set -o errexit -o nounset -o pipefail
        cd ~
        confit.CD//78108f633935aefe//inner
      )
    }
    function confit.CD//78108f633935aefe//inner {
      GitCheckout//4dfbe151486ae2d6
      confit.CD//2f09153924b83023
    }



    SolidsnackDots//5386fae40f7eb977

The names of the generated bash functions are derived from the qualified names
of the task classes, with a hash appended. The hash depends on the arguments
passed to the class and any transformers applied -- it should remain the same
from run to run.
