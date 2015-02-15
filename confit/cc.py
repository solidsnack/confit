"""
A collection of generally useful configurations, as well as confit's core
definitions. If you're writing a system, configuration you probably want this
module.
"""

import binascii
import os
import pipes
import re
import StringIO
import sys
import textwrap
import types
import uu

from .task import *     # Import Task() and friends, to ease defining new tasks
from .bash import *                                          # Pull in wrappers


# # # # # # # # # # # # # # # # Config Collection # # # # # # # # # # # # # # # 
# # # # # # # # # library of generally useful tasks and helpers # # # # # # # #


def untq(string):
    """Reformat and outdent a triple quoted string

    Removes an initial newline, if present.
    """
    return Bash.untq(string)


# ##################################################### # # # # # # # # # # # #
# ##################################################### Tasks for most any *nix


class WriteFile(Task):
    """Write a file to the given location on disk."""
    def __init__(self, path, content=None, mode=None, owner=None):
        self.__dict__.update(locals())
        del self.self

    def code(self):
        return [
            self.create(),
            ["chmod", self.mode, self.path] if self.mode else None,
            ["chown", self.owner, self.path] if self.owner else None
        ]

    def create(self):
        """Bash fragment implementing file creation.
        
        If no content is passed, we use ``touch`` to create the file.

        If content is passed, then the file is created with ``cat`` if the
        contents are plain text or ``uudecode`` if the contents are binary
        (which for us means: the contents contain ASCII null or ASCII tab).
        """
        if self.content is None:
            return ['touch', self.path]
        else:
            if '\0' not in self.content and '\t' not in self.content:
                hex_delimiter = binascii.b2a_hex(os.urandom(16))
                template = 'cat > {path} \\\n<<-\\{eof}\n{content}\n{eof}'
                text = template.format(path=pipes.quote(self.path),
                                       content=self.content,
                                       eof=('EOF//%s' % hex_delimiter))
            else:
                i, o = StringIO.StringIO(self.content), StringIO.StringIO()
                uu.encode(i, o, '/dev/stdout')
                template = 'uudecode > {path} \\\n<<-\\uu\n{content}\nuu'
                text = template.format(path=pipes.quote(self.path),
                                       content=o.getvalue())
            return '\n\t'.join(text.split('\n'))


class TZ(Task):
    """Set system timezone."""
    def __init__(self, tz='UTC'):
        self.__dict__.update(locals())
        del self.self

    def code(self):
        tz_path = '/usr/share/zoneinfo/%s' % pipes.quote(self.tz)
        return [['ln', '-nsf', '/etc/localtime', tz_path]]


# ################################################### # # # # # # # # # # # # #
# ################################################### Tasks for Ubuntu & Debian


class Apt(Task):
    """Install a package with Apt."""
    def __init__(self, package):
        self.__dict__.update(locals())
        del self.self

    def code(self):
        return [['apt-get', 'install', '-y', self.package]]


class EnDK(Task):
    """Create and enable the en_DK.UTF-8 locale."""
    def code(self):
        return """
        local vars=(LANG=en_DK.UTF-8
                    LC_MONETARY=en_US.UTF-8
                    LC_NUMERIC=en_US.UTF-8)
        locale-gen en_DK.UTF-8
        update-locale "${vars[@]}"
        export "${vars[@]}"
        """


# ################################################################# # # # # # #
# ################################################################ Quirky tasks


class Sudoers(WriteFile):
    """Simplify Sudo permissions."""
    path = '/etc/sudoers.d/an-it-harm-none-do-what-ye-will'
    mode = '0440'
    owner = 'root:root'
    content = untq("""
        Defaults !authenticate, !lecture, !mail_badpass, !env_reset

        root    ALL=(ALL) ALL
        %sudo   ALL=(ALL) ALL
    """)

    def __init__(self):
        pass


# ########################################################### # # # # # # # # #
# ########################################################## Export non-modules

__all__ = [name for name, d in locals().items() if type(d) != types.ModuleType]
