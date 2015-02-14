import binascii
import os
import pipes
import StringIO
import textwrap
import uu

from .task import Task


# ##################################################### # # # # # # # # # # # #
# ##################################################### Tasks for most any *nix


class WriteFile(Task):
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
                template = 'uudecode > {path} <<-\\uu\n{content}\nuu'
                text = template.format(path=pipes.quote(self.path),
                                       content=o.getvalue())
            return '\n\t'.join(text.split('\n'))


class TZ(Task):
    def __init__(self, tz='UTC'):
        self.__dict__.update(locals())
        del self.self

    def code(self):
        tz_path = '/usr/share/zoneinfo/%s' % pipes.quote(self.tz)
        return [['ln', '-nsf', '/etc/localtime', tz_path]]


# ################################################### # # # # # # # # # # # # #
# ################################################### Tasks for Ubuntu & Debian


class Apt(Task):
    def __init__(self, package):
        self.__dict__.update(locals())
        del self.self

    def code(self):
        return [['apt-get', 'install', '-y', self.package]]


class EnDK(Task):
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
    path = '/etc/sudoers.d/an-it-harm-none-do-what-ye-will'
    mode = '0440'
    owner = 'root:root'
    content = textwrap.dedent("""
        Defaults !authenticate, !lecture, !mail_badpass, !env_reset

        root    ALL=(ALL) ALL
        %sudo   ALL=(ALL) ALL
    """[1:])

    def __init__(self):
        pass
