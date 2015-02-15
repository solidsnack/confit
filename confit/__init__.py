"""
This minimal entry point for confit exports the core task abstractions.
"""

import types

from .task import *
from .bash import *


__all__ = [name for name, d in locals().items() if type(d) != types.ModuleType]
