import itertools
import os
import pipes
import re
import sys
import textwrap

from .bash import Bash, ButOnce, Wrapper


class Task(ButOnce):
    """A task is an idempotent chunk of Bash code.

    Tasks can depend on other tasks, or on tasks within wrappers.

    To implement a new task, override ``.dependencies`` to return a collection
    of dependencies and override ``.code`` to return an array of argument
    vectors or plain strings (the latter will be interpreted as literal Bash,
    subject to shell expansion). One can also return a single string from
    ``.code``, which will be interpreted as though an array with a single
    argument had been returned.
    """

    def __init__(self):
        pass

    def deps(self):
        """Direct dependencies."""
        return set()

    def code(self):
        """Code to run when dependencies are fulfilled."""
        return []

    @property
    def decls(self):
        if len(self.deps()) > 0:
            calls = ['  ' + dep.call for dep in self.deps()]
            pre = '\n'.join(['function %s {' % self.pre] + calls + ['}'])
            return super(Task, self).decls + [pre]
        else:
            return super(Task, self).decls

    @property
    def pre(self):
        """Name of function which calls all dependencies."""
        return '%s//pre' % self.name

    @property
    def body(self):
        code = self.code()
        if isinstance(code, basestring) or isinstance(code, Bash.Raw):
            code = [code]
        return self.checks + [self.pre if len(self.deps()) > 0 else None] + code

    def to_script(self, verbose=False, debug=False, locale='en_US.UTF-8'):
        def all_defs(task):
            subs = task.others if isinstance(task, Wrapper) else task.deps()
            return itertools.chain(subs, *[all_defs(t) for t in subs])

        def split(task):
            return re.split(r'[.]|//', task.name)

        tasks = set(all_defs(self))
        tasks |= set([self])
        decls = [t.decls for t in sorted(tasks, key=split)]
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
