import itertools
import os
import pipes
import re
import stat
import tempfile
import textwrap

from .meta import Specced


class Bash(Specced):
    """A Bash code chunk, optionally with arguments."""

    @staticmethod
    def fmt(chunk):
        if isinstance(chunk, Bash.Raw):
            return chunk.string
        if isinstance(chunk, basestring):
            # Block of Bash code, maybe with tab-prefixed Bash HEREDOCs,
            # maybe in a Python triple-quoted string.
            dedented = textwrap.dedent(re.sub(r'^\n ', ' ', chunk)).strip()
            return re.sub(r'^([^\t])', r'  \1', dedented, flags=re.MULTILINE)
        # Array of arguments, which should be properly escaped.
        return '  ' + ' '.join(pipes.quote(s) for s in arg)

    def __init__(self, code, *args):
        """Construct a callable Bash code object.

        If the code argument is an array, each argument is handled as literal
        Bash code if it is a string or as an array of arguments to be escaped
        before insertion if it is an array. In either case, it is indented
        before being inserted.

        If the code argument is a string, it is treated as though an array of
        one string argument had been passed in.
        """
        if isinstance(code, basestring) or isinstance(code, Bash.Raw):
            code = [code]
        self.__dict__.update(locals())
        del self.self

    @property
    def decls(self):
        """Function definition (or definitions) for this Bash object."""
        body = '\n'.join(Bash.fmt(item) for item in self.body if item)
        return ['\n'.join(['function %s {' % self.name, body, '}'])]

    @property
    def call(self):
        if hasattr(self, 'args'):
            args = [pipes.quote(arg) for arg in self.args]
        else:
            args = []
        return ' '.join([self.name] + args)

    @property
    def body(self):                             # To be overriden by subclasses
        """Override body to add code to the function body."""
        return self.code

    def script(self, verbose=False, debug=False, locale='en_US.UTF-8'):
        return textwrap.dedent("""
            #!/bin/bash
            set -o errexit -o nounset -o pipefail

            export LC_ALL={locale}

            {decls}

            {debug}
            {call}
        """[1:]).format(call=self.call,
                        locale=locale,
                        debug=('set -o xtrace' if debug else ''),
                        # verbose=('export __V__=true' if verbose else ''),
                        decls='\n'.join(self.decls))

    def run(self, *args, **kwargs):
        # TODO: Reimplement by spawning a Bash shell and passing self over.
        #       This way, we needn't write a file to disk.
        with tempfile.NamedTemporaryFile(suffix='.bash') as h:
            h.write(self.to_script(*args, **kwargs))
            h.flush()
            os.chmod(h.name, stat.S_IRUSR | stat.S_IXUSR)
            os.system(h.name)

    class Raw(object):
        """A string of Bash which is not to be formatted.

        In order to produce well-formatted function definitions, the formatter
        indents Bash that is passed as a string (though it does not put spaces
        in front of tabs, to support indented HEREDOCs). To prevent this from
        happening, pass a ``Raw`` object instead of a string.

        You probably won't ever need to do this but just in case...
        """
        def __init__(self, string):
            self.__dict__.update(locals())
            del self.self


class ButOnce(Bash):
    """The body of a ButOnce will be executed only once per run."""
    @property
    def body(self):
        return self.checks + [divider] + self.code

    @property
    def checks(self):
        """Override check to add more checks."""
        sentinel = 'called_%016x' % abs(hash(self))
        check = """
            if [[ ${{{sentinel}:+isset}} ]]
            then return
            else {sentinel}=true
            fi
        """.format(sentinel=sentinel)
        return [check]


class Wrapper(Bash):
    """Calls wrapped Bash in a new environment.

    A wrapper gains a ``.__call__()`` that can be called on another Bash
    object or a collection of Bash objects to run them in a changed
    environment.
    """
    def __call__(self, others):
        if isinstance(others, Task):
            others = [others]
        for task in others:
            task._callspec_labels |= set(self._callspec)
        self.others = others
        return self

    @property
    def decls(self):
        calls = ['  ' + other.call for other in self.others]
        inner = '\n'.join(['function %s {' % self.inner] + calls + ['}'])
        return super(Wrapper, self).decls + [inner]

    @property
    def inner(self):
        """Name for function which calls all wrapped tasks."""
        return '%s//inner' % self.name

    @property
    def body(self):
        return [self.inner]


class Sudo(Wrapper):
    """Run the wrapped tasks with Sudo."""

    def __init__(self, user=None):
        self.__dict__.update(locals())
        del self.self

    @property
    def body(self):
        return ["""
        {{ declare -f {inner} {names}
          echo set -o errexit -o nounset -o pipefail
          echo {inner}
        }} | {sudo}
        """.format(names=' '.join(other.name for other in self.others),
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
