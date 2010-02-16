#===============================================================================
# Copyright 2010 Matt Chaput
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

import optparse
from functools import wraps
from inspect import getargspec


def clean_docstring(doc):
    doc = doc.replace("\t", " " * 8)
    lines = doc.split("\n")
    minindent = 9999
    for line in lines[1:]:
        indent = len(line) - len(line.lstrip())
        if indent < minindent:
            minindent = indent
        if indent == 0: break
    lines = [line[minindent:] for line in lines]
    return "\n".join(lines)

def totype(v, default):
    t = type(default)
    if t is int:
        return int(v)
    elif t is float:
        return float(v)
    elif t is long:
        return long(v)
    else:
        return v


class CommandError(Exception): pass


class Cmd(object):
    def __init__(self, fn, argnames, keywords,
                 vargsname, kwargsname, docstring):
        self.fn = fn
        self.argnames = argnames
        self.keywords = keywords
        self.vargsname = vargsname
        self.kwargsname = kwargsname
        self.docstring = docstring


class Baker(object):
    def __init__(self):
        self.commands = {}
        self.defaultcommand = None
    
    def command(self, fn=None, default=False):
        if fn is None:
            return lambda fn: self.command(fn, default=default)
        else:
            arglist, vargsname, kwargsname, defaults = getargspec(fn)
            argnames = arglist[:len(defaults)]
            keywords = dict(zip(arglist[0-len(defaults):], defaults))
            cmd = Cmd(fn, argnames, keywords, vargsname, kwargsname,
                      fn.__doc__)
            self.commands[fn.__name__] = cmd
            if default: self.defaultcommand = cmd
    
    def run(self, argv):
        if len(argv) > 1 and argv[1] in self.commands:
            cmd = self.commands[argv[1]]
            argv.pop(0)
        else:
            cmd = self.defaultcommand
            if cmd is None:
                raise CommandError("No command specified")
        args, kwargs = self.parse_args(cmd, argv[1:])
        print args, kwargs
    
    def parse_args(self, cmd, argv):
        keywords = cmd.keywords
        char2keyword = dict((name[0], name) for name in keywords.iterkeys())
        
        vargs = []
        kwargs = keywords.copy()
        
        while argv:
            arg = argv.pop(0)
            if arg == "-":
                vargs.extend(argv)
                break
            
            elif arg == "--":
                continue
            
            elif arg.startswith("--"):
                eq = None
                if "=" in arg:
                    eq = arg.find("=")
                    name = arg[2:eq]
                else:
                    name = arg[2:]
                    
                if name not in keywords:
                    raise CommandError("Unknown keyword option --%s" % name)
                
                default = keywords[name]
                if type(default) is bool:
                    value = not default
                else:
                    try:
                        if eq:
                            value = arg[eq+1:]
                        else:
                            value = argv.pop(0)
                        value = totype(value, default)
                    except TypeError:
                        raise CommandError("Couldn't convert %s value %r to type %s" % (name, value, type(default)))
                kwargs[name] = value
                
            elif arg.startswith("-"):
                for i in xrange(1, len(arg)):
                    char = arg[i]
                    if char not in char2keyword:
                        raise CommandError("Unknown option -%s" % char)
                    name = char2keyword[char]
                    default = keywords[name]
                    if type(default) is bool:
                        kwargs[name] = not default
                    else:
                        if i == len(arg)-1:
                            kwargs[name] = totype(argv.pop(0), default)
                            break
                        else:
                            kwargs[name] = totype(arg[i+1:], default)
                            break
            
            else:
                vargs.append(arg)
                
        return vargs, kwargs
                        

_baker = Baker()
command = _baker.command
run = _baker.run


@command(default=True)
def hello(a, b, c=False, d='bloog', e=200, *args, **kwargs):
    "help string"
    print "hello"


if __name__ == "__main__":
    import sys
    run(sys.argv)







