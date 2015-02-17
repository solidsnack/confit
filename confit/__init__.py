"""
This minimal entry point for confit exports the core task abstractions, but no
utility classes or members of the task library.
"""

import itertools
import os
import pipes
import re
import stat
import sys
import tempfile
import textwrap
import types

from .meta import *


class Bash(Specced):
    """A Bash code chunk, optionally with arguments."""

    @staticmethod
    def fmt(chunk):
        if isinstance(chunk, Bash.Raw):
            return chunk.string
        if isinstance(chunk, basestring):
            # Block of Bash code, maybe with tab-prefixed Bash HEREDOCs,
            # maybe in a Python triple-quoted string.
            dedented = Bash.untq(chunk)
            return re.sub(r'^([^\t])', r'  \1', dedented, flags=re.MULTILINE)
        # Array of arguments, which should be properly escaped.
        return '  ' + ' '.join(pipes.quote(s) for s in chunk)

    @staticmethod
    def untq(string):
        """Outdent triple-quoted strings.

        A leading newline, if present, is stripped.
        """
        string = string[1:] if string[0:1] == '\n' else string
        return textwrap.dedent(string).strip()

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
    def names(self):
        """Names of function definition (or definitions).

        This might include any number of names of other functions, if this
        Bash object calls them.
        """
        return set([self.name])

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
        sentinel = '_%016x' % abs(hash(self))
        check = """
            [[ ${{{sentinel}+_}} ]] && return || {sentinel}=_ # only once
        """.format(sentinel=sentinel)
        return [check]


class Wrapper(Bash):
    """Calls wrapped Bash in a new environment.

    A wrapper gains a ``.__call__()`` that can be called on another Bash
    object or a collection of Bash objects to run them in a changed
    environment.
    """
    def __call__(self, *others):
        chained = []
        for other in others:
            if isinstance(other, Bash):
                chained += [other]
            else:
                chained += list(other)

        for other in chained:
            self._callspec_labels |= set([other._callspec])
            self._callspec_labels |= other._callspec_labels
            other._callspec_labels |= set(self._callspec)

        self.others = chained
        return self

    @property
    def decls(self):
        calls = ['  ' + other.call for other in self.others]
        inner = '\n'.join(['function %s {' % self.inner] + calls + ['}'])
        return super(Wrapper, self).decls + [inner]

    @property
    def names(self):
        names = set([self.name, self.inner])
        for other in self.others:
            names |= other.names
        return names

    @property
    def inner(self):
        """Name for function which calls all wrapped tasks."""
        return '%s//inner' % self.name

    @property
    def body(self):
        return [self.inner]


class Task(ButOnce):
    """A task is an idempotent chunk of Bash code.

    Tasks can depend on other tasks, or on tasks within wrappers.

    To implement a new task, override ``.deps`` to return a collection of
    dependencies and override ``.code`` to return an array of argument vectors
    or plain strings (the latter will be interpreted as literal Bash, subject
    to shell expansion). One can also return a single string from ``.code``,
    which will be interpreted as though an array with a single argument had
    been returned.  """

    def __init__(self):
        pass

    def deps(self):
        """Direct dependencies."""
        return set()

    def code(self):
        """Code to run when dependencies are fulfilled."""
        return [': # Do nothing.']

    @property
    def decls(self):
        if len(self.deps()) > 0:
            calls = ['  ' + dep.call for dep in self.deps()]
            pre = '\n'.join(['function %s {' % self.pre] + calls + ['}'])
            return super(Task, self).decls + [pre]
        else:
            return super(Task, self).decls

    @property
    def names(self):
        """Names of this task's functions and those of all dependencies."""
        names = [self.name, self.pre] if len(self.deps()) > 0 else [self.name]
        names = set(names)
        for other in self.subs:
            names |= other.names
        return names

    @property
    def subs(self):
        """All tasks in the dependency graph (full subtree)."""
        def all_defs(task):
            subs = []
            if isinstance(task, Wrapper):
                subs += task.others
            if isinstance(task, Task):
                subs += task.deps()
            return itertools.chain(subs, *[all_defs(t) for t in subs])
        return set(all_defs(self))

    @property
    def pre(self):
        """Name of function which calls all dependencies."""
        return '%s//pre' % self.name

    @property
    def body(self):
        checks = self.checks
        code = self.code()
        if isinstance(code, basestring) or isinstance(code, Bash.Raw):
            code = [code]
        return checks + [self.pre if len(self.deps()) > 0 else None] + code

    def script(self, verbose=False, debug=False, locale='en_US.UTF-8'):
        def all_defs(task):
            subs = []
            if isinstance(task, Wrapper):
                subs += task.others
            if isinstance(task, Task):
                subs += task.deps()
            return itertools.chain(subs, *[all_defs(t) for t in subs])

        tasks = set([self]) | self.subs
        decls = [t.decls for t in sorted(tasks, key=Named.components)]
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
                        decls='\n\n'.join('\n'.join(group) for group in decls))


# TODO: Transformers. Tasks that can wrap other tasks. So, launch a server,
#       then run the tasks on that server...


__all__ = [name for name, decl in locals().items()
           if not isinstance(decl, types.ModuleType)]
