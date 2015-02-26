import collections
import inspect
import json


class Named(object):
    @property
    def name(self):
        name = Named.typename(self.__class__)
        hex_hash = '%016x' % abs(hash(self))
        return '%s//%s' % (name, hex_hash)

    @staticmethod
    def typename(typ):
        module = typ.__module__
        module = module + '.' if module not in [None, '__main__'] else ''
        return module + typ.__name__

    @staticmethod
    def components(name):
        name = name.name if isinstance(name, Named) else name
        def subkey(s):
            return tuple(s.split('//')) if '//' in s else s
        return tuple(subkey(s) for s in name.split('.'))

    @property
    def sortkey(self):
        return Named.components(self.name)


class ClassHierarchyRoot(object):
    @classmethod
    def subclasses(cls):
        subs = cls.__subclasses__()
        return set(subs) | {c for s in subs for c in s.subclasses()}


class Specced(Named):
    def __new__(typ, *args, **kwargs):
        spec = CallSpec(typ.__init__, *args, **kwargs)
        o = object.__new__(typ, *args, **kwargs)
        o._callspec = (Named.typename(typ), spec)
        o._callspec_labels = set()
        return o

    def __repr__(self):
        name, spec = self._callspec
        args = ', '.join('%s=%r' % (k, v) for k, v in spec.items())
        return '%s(%s)' % (name, args)

    @property
    def key(self):
        return (self._callspec, frozenset(self._callspec_labels))

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        return self.key == other.key

    def __ne__(self, other):
        return self.key != other.key

    def __gt__(self, other):                # Greater than means: more specific
        return self.key > other.key            # Should be the other way around

    def __ge__(self, other):
        return self.key >= other.key

    def __lt__(self, other):
        return self.key < other.key

    def __le__(self, other):
        return self.key <= other.key


class CallSpec(collections.OrderedDict):
    """Match names to arguments for the given function."""
    def __init__(self, f, *varargs, **keywords):
        spec = inspect.getargspec(f)
        names = spec.args[1:] if inspect.ismethod(f) else spec.args
        named = zip(names, varargs)
        varargs = varargs[len(named):]
        named += [(name, keywords[name]) for name in names if name in keywords]
        for name in names:
            if name in keywords:
                del keywords[name]
        if len(varargs) > 0:
            if not spec.varargs:
                raise ValueError('Varargs are not supported by %r' % f)
            named += [(spec.varargs, varargs)]
        if len(keywords) > 0:
            if not spec.keywords:
                msg = 'Extended keyword arguments are not supported by %r' % f
                raise ValueError(msg)
            named += [(spec.keywords, keywords)]
        super(CallSpec, self).__init__(named)

    def __hash__(self):
        return hash(json.dumps(self, sort_keys=True))

    def __eq__(self, other):       # Self specifies the same arguments as other
        return self <= other and not self < other

    def __ne__(self, other):
        return not self == other

    def __gt__(self, other):
        return other < self

    def __ge__(self, other):
        return other <= self

    def __lt__(self, other):
        return set(self.keys()) < set(other.keys()) and self <= other

    def __le__(self, other):             # Self is not more specific than other
        if set(self.keys()) <= set(other.keys()):
            for k in self.keys():
                if self[k] != other[k]:
                    return False
            return True
        return False
