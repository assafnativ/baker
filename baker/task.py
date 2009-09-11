#===============================================================================
# Copyright 2009 Matt Chaput
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#===============================================================================

from functools import wraps
from inspect import currentframe, getargspec


#def caller_locals():
#    f = currentframe(1)
#    lcls = f.f_locals


class Target():
    def __init__(self, fn=None, depends=None):
        if isinstance(depends, basestring):
            depends = [depends]
        elif depends is None:
            depends = []
        self.depends = depends
        
        if callable(fn):
            self(fn)
        elif fn is not None:
            raise Exception("Unexpected first argument to target: %r" % fn)
    
    @staticmethod
    def _cleandoc(doc):
        docstring = doc.replace("\t", " " * 8)
        lines = doc.split("\n")
        minindent = 9999
        for line in lines[1:]:
            indent = len(line) - len(line.lstrip())
            if indent < minindent:
                minindent = indent
            if indent == 0:
                break
        lines = [line[minindent:] for line in lines]
        return "\n".join(lines)
    
    def __call__(self, fn):
        print "Called with:", fn
        self.function = fn
        for name in ("__module__", "__doc__"):
            setattr(self, name, getattr(fn, name))
        self.name = fn.__name__
        
        args, vargs, self.sectionarg, defaults = getargspec(fn)
        if vargs:
            raise Exception("Can't use *args in a target function")
        
        diff = len(args) - len(defaults)
        self.positionals = args[:diff]
        self.keywords = dict(zip(args[diff:], defaults))
        
        return self
    
    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.name)
    
    def run(self, env):
        # Run dependency targets first
        for dep in self.depends:
            if not dep in env.hasrun:
                dep.run(env)
        
        args = []
        for name in self.positionals:
            if name in env:
                args.append(env[name])
            else:
                raise Exception("Target %r requires %r argument" % (self.name, name))
        
        #ret = self.function(*args, **kwargs)
        #env.set_return(self.name, ret)
        

    
@Target(depends=('hola', 'guttentag'))
def test(hello, quiet=False, user="matt"):
    print "Hi there"

print "test=", test


x = 10
def t1():
    print "locals=", locals()
    f = currentframe(1)
    print "locals(1)=", f.f_locals

def t2():
    x = 20
    t1()
    
t2()




