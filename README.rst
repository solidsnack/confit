---------------
Getting Started
---------------

* Install

.. code-block:: bash

    pip install https://github.com/solidsnack/confit/archive/master.zip

* Write a class that subclasses ``Task``

.. code-block:: python

    import confit

    class Dots(confit.Task):
        ...

* Call ``.script()`` to generate a Bash script, to run locally or remotely.
