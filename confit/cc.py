"""
A collection of generally useful configurations, as well as confit's core
definitions. If you're writing a system, configuration you probably want this
module.
"""

import binascii
import itertools
import os
import pipes
import re
import StringIO
import sys
import textwrap
import types
import uu

from . import *


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
    def __init__(self, path, content=None, mode=None, owner=None, mkdir=True):
        self.__dict__.update(locals())
        del self.self

    def code(self):
        return [
            self.mkdir_p(),
            self.create(),
            ['chmod', self.mode, self.path] if self.mode else None,
            ['chown', self.owner, self.path] if self.owner else None
        ]

    def mkdir_p(self):
        if self.mkdir:
            dirname = os.path.dirname(self.path)
            if dirname not in ['.', '..']:
                return ['mkdir', '-p', dirname]

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
# ##################################### Tasks that display a decided preference


class Sudoers(WriteFile):
    """Simplify Sudo permissions."""
    path = '/etc/sudoers.d/an-it-harm-none-do-what-ye-will'
    mode = '0440'
    owner = 'root:root'
    mkdir = False
    content = untq("""
        Defaults !authenticate, !lecture, !mail_badpass, !env_reset

        root    ALL=(ALL) ALL
        %sudo   ALL=(ALL) ALL
    """)

    def __init__(self):
        pass


# ############################################################# # # # # # # # #
# ############################################################# Useful wrappers


class Sudo(Wrapper):
    """Run the wrapped tasks with Sudo."""

    def __init__(self, user=None):
        self.__dict__.update(locals())
        del self.self

    @property
    def body(self):
        names = sorted(self.names, key=Named.components)
        return ["""
        {{ declare -f {inner} {names}
          echo set -o errexit -o nounset -o pipefail
          echo {inner}
        }} | {sudo}
        """.format(names=' '.join(names),
                   inner=self.inner,
                   sudo=self.sudo)]

    @property
    def sudo(self):
        if self.user is not None:
            return 'sudo -u %s bash' % pipes.quote(user)
        else:
            return 'sudo bash'


class PopSudo(Sudo):
    """Pop one layer of Sudo nesting (if present)."""
    def __init__(self):
        pass

    @property
    def sudo(self):
        return """
        if [[ ${SUDO_USER:+isset} ]]
        then sudo -u "${SUDO_USER}" bash
        else bash
        fi
        """


class CD(Wrapper):
    """Change directory and then run code.

    By default, shell expansion is allowed, to facilitate things like ``cd ~``
    or ``cd $HADOOP_HOME``.
    """
    def __init__(self, directory, allow_shell_expansion=True):
        self.__dict__.update(locals())
        del self.self

    @property
    def body(self):
        if self.allow_shell_expansion:
            directory = self.directory
        else:
            directory = pipes.quote(self.directory)
        return ["""
        ( set -o errexit -o nounset -o pipefail
          cd {directory}
          {inner}
        )
        """.format(directory=directory, inner=self.inner)]


class Env(Wrapper):
    """Set environment variables when tasks are run."""
    def __init__(self, **env):
        self.__dict__.update(locals())
        del self.self

    @property
    def body(self):
        decls = ['export %s=%s' % (pipes.quote(var), pipes.quote(val))
                 for var, val in sorted(self.env.items())]
        return ["""
        ( set -o errexit -o nounset -o pipefail
          {decls}
          {inner}
        )
        """.format(decls='\n  '.join(decls), inner=self.inner)]


# ########################################################### # # # # # # # # #
# ########################################################## Export non-modules

__all__ = [name for name, decl in locals().items()
           if not isinstance(decl, types.ModuleType)]
