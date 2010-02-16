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

import os, re, sys
from inspect import getargspec
from textwrap import wrap, fill


def normalize_docstring(docstring):
    return re.sub(r"[\r\n\t ]+", " ", docstring).strip()


param_exp = re.compile(r"^([\t ]*):param (.*?): ([^\n]*\n(\1[ \t]+[^\n]*\n)*)",
                       re.MULTILINE)

def find_param_docs(docstring):
    paramdocs = {}
    for match in param_exp.finditer(docstring):
        name = match.group(2)
        value = match.group(3)
        paramdocs[name] = value

def remove_param_docs(docstring):
    return param_exp.sub("", docstring)


def totype(v, default):
    t = type(default)
    if t is int:
        return int(v)
    elif t is float:
        return float(v)
    elif t is long:
        return long(v)
    elif t is bool:
        lv = v.lower()
        if lv in ("true", "yes", "on", "1"):
            return True
        elif lv in ("false", "no", "off", "0"):
            return False
        else:
            raise TypeError
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
    
    def command(self, fn=None, default=False, params=None):
        if fn is None:
            return lambda fn: self.command(fn, default=default, params=params)
        else:
            arglist, vargsname, kwargsname, defaults = getargspec(fn)
            docstring = fn.__doc__ or ""
            
            if params is None:
                if hasattr(fn, "func_annotations") and fn.func_annotations:
                    params = fn.func_annotations
                else:
                    params = find_param_docs(docstring)
                    docstring = remove_param_docs(docstring)
            
            argnames = arglist[:len(defaults)]
            if argnames[0] == "self":
                argnames.pop(0)
            keywords = dict(zip(arglist[0-len(defaults):], defaults))
            cmd = Cmd(fn, argnames, keywords, vargsname, kwargsname,
                      docstring)
            self.commands[fn.__name__] = cmd
            
            if default: self.defaultcommand = cmd
    
    def print_top_help(self, scriptname, file=sys.stdout):
        cmdnames = sorted(self.commands.keys())
        maxlen = max(len(name) for name in cmdnames) + 3
        
        file.write("\nUsage: %s COMMAND <options>\n\n" % scriptname)
        print("Available commands:\n\n")
        for cmdname in cmdnames:
            cmd = self.commands[cmdname]
            docstring = normalize_docstring(cmd.docstring)
            lines = wrap(docstring, 78-maxlen)
            tab = " " * (maxlen - (len(cmdname)+1))
            file.write(" " + cmdname + tab)
            if lines:
                file.write(lines[0] + "\n")
                for line in lines[1:]:
                    file.write((" " * maxlen) + line + "\n")
        file.write("\n")
        file.write('Use "%s COMMAND --help" for individual command help.\n' % scriptname)
        sys.exit(0)
    
    def run(self, argv):
        if (len(argv) < 2) or (argv[1] == "-h" or argv[1] == "--help"):
            self.print_top_help(argv[0])
        elif len(argv) > 1 and argv[1] in self.commands:
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
            if arg == "-h" or arg == "--help":
                self.print_command_help(cmd)
            
            elif arg == "-":
                vargs.extend(argv)
                break
            
            elif arg == "--":
                continue
            
            elif arg.startswith("--"):
                value = None
                if "=" in arg:
                    name, value = arg[2:].split("=", 1)
                else:
                    name = arg[2:]
                
                if name not in keywords:
                    raise CommandError("Unknown keyword option --%s" % name)
                
                if value is None:
                    default = keywords[name]
                    if type(default) is bool:
                        value = not default
                    else:
                        value = argv.pop(0)
                try:
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
    """This is a help string
    
    :param a: the thing
    :param b: another thing
        that's sort of like
        the first thing
    :param c: something nothing at all like the first thing.
    """
    print "hello"

@command
def second(name, value="", overwrite=False):
    """This command sets the named key in the database to the given value, or
    if no value is specified, removes the key from the database. The --overwrite
    option controls whether the key will be overwritten if it already exists
    in the database (the default is to not overwrite).
    """
    
    print "name=", name, "set=", set


if __name__ == "__main__":
    import sys
    run(sys.argv)







