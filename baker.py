#=============================================================================
# Copyright 2012 Matt Chaput
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
#=============================================================================

import re
import os
import sys
import gzip
import bz2
from collections import namedtuple
from inspect import getargspec
from textwrap import wrap

if sys.version_info[:2] < (3, 0):
    range = xrange


# Stores metadata about a command
Cmd = namedtuple("Cmd", ["name", "fn", "argnames", "keywords", "shortopts",
                         "has_varargs", "has_kwargs", "docstring",
                         "paramdocs", "is_method"])

param_exp = re.compile(r"^([\t ]*):param (.*?): ([^\n]*\n(\1[ \t]+[^\n]*\n)*)",
                       re.MULTILINE)


def normalize_docstring(docstring):
    """Normalizes whitespace in the given string.
    """
    return re.sub(r"[\r\n\t ]+", " ", docstring).strip()


def find_param_docs(docstring):
    """Finds ReStructuredText-style ":param:" lines in the docstring and
    returns a dictionary mapping param names to doc strings.
    """
    paramdocs = {}
    for match in param_exp.finditer(docstring):
        name = match.group(2)
        value = match.group(3)
        paramdocs[name] = value
    return paramdocs


def remove_param_docs(docstring):
    """Finds ReStructuredText-style ":param:" lines in the docstring and
    returns a new string with the param documentation removed.
    """
    return param_exp.sub("", docstring)


def process_docstring(docstring):
    """Takes a docstring and returns a list of strings representing
    the paragraphs in the docstring.
    """
    lines = docstring.split("\n")
    paras = [[]]
    for line in lines:
        if not line.strip():
            paras.append([])
        else:
            paras[-1].append(line)
    paras = [normalize_docstring(" ".join(ls)) for ls in paras if ls]
    return paras


def format_paras(paras, width, indent=0, lstripline=[]):
    """Takes a list of paragraph strings and formats them into a word-wrapped,
    optionally indented string.
    """
    output = []
    for para in paras:
        lines = wrap(para, width - indent)
        if lines:
            for line in lines:
                output.append((" " * indent) + line)
    for i in lstripline:
        output[i] = output[i].lstrip()
    return output


def totype(v, default):
    """Tries to convert the value 'v' into the same type as 'default'.
    """
    if isinstance(default, bool):
        lv = v.lower()
        if lv in ("true", "yes", "on", "1"):
            return True
        elif lv in ("false", "no", "off", "0"):
            return False
        raise TypeError
    elif isinstance(default, int):
        return int(v)
    elif isinstance(default, float):
        return float(v)
    return v


class CommandError(Exception):
    """General exception for Baker errors, usually related to parsing the
    command line.
    """
    def __init__(self, msg, scriptname, cmd=None):
        Exception.__init__(self, msg)
        self.scriptname = scriptname
        self.commandname = cmd


class TopHelp(Exception):
    """Exception raised by Baker.parse() to indicate the user requested the
    overall help for the script, e.g. by typing "script.py help" or
    "script.py --help"
    """
    def __init__(self, scriptname):
        self.scriptname = scriptname


class CommandHelp(Exception):
    """Exception raised by baker.parse() to indicate the user requested help
    for a specific command, e.g. by typing "script.py command --help" or
    "script.py help command".
    """
    def __init__(self, scriptname, cmd):
        self.scriptname = scriptname
        self.cmd = cmd


class Baker(object):
    def __init__(self):
        self.commands = {}
        self.defaultcommand = None

    def command(self, fn=None, name=None, default=False,
                params=None, shortopts=None):
        """Registers a command with the bakery. This does not call the
        function, it simply adds it to the list of functions this Baker
        knows about.

        This method is usually used as a decorator::

            b = Baker()

            @b.command
            def test():
                pass

        :param fn: the function to register.
        :param name: use this argument to register the command under a
            different name than the function name.
        :param default: if True, this command is used when a command is not
            specified on the command line.
        :param params: a dictionary mapping parameter names to docstrings. If
            you don't specify this argument, parameter annotations will be used
            (Python 3.x only), or the functions docstring will be searched for
            Sphinx-style ':param' blocks.
        :param shortopts: a dictionary mapping parameter names to short
            options, e.g. {"verbose": "v"}.
        """
        # This method works as a decorator with or without arguments.
        if fn is None:
            # The decorator was given arguments, e.g. @command(default=True),
            # so we have to return a function that will wrap the function when
            # the decorator is applied.
            return lambda fn: self.command(fn, default=default,
                                           name=name,
                                           params=params,
                                           shortopts=shortopts)
        else:
            name = name or fn.__name__

            # Inspect the argument signature of the function
            arglist, vargsname, kwargsname, defaults = getargspec(fn)
            has_varargs = bool(vargsname)
            has_kwargs = bool(kwargsname)

            # Get the function's docstring
            docstring = fn.__doc__ or ""

            # If the user didn't specify parameter help in the decorator
            # arguments, try to get it from parameter annotations (Python 3.x)
            # or RST-style :param: lines in the docstring
            if params is None:
                if hasattr(fn, "func_annotations") and fn.func_annotations:
                    # Python 3.x
                    params = fn.func_annotations
                else:
                    params = find_param_docs(docstring)
                    docstring = remove_param_docs(docstring)

            # If the user didn't specify
            shortopts = shortopts or {}

            # Zip up the keyword argument names with their defaults
            if defaults:
                keywords = dict(zip(arglist[0 - len(defaults):], defaults))
            else:
                keywords = {}

            # If this is a method, remove 'self' from the argument list
            is_method = False
            if arglist and arglist[0] == "self":
                is_method = True
                arglist.pop(0)

            # Create a Cmd object to represent this command and store it
            cmd = Cmd(name, fn, arglist, keywords, shortopts, has_varargs,
                      has_kwargs, docstring, params, is_method)
            self.commands[name] = cmd

            # If default is True, set this as the default command
            if default:
                self.defaultcommand = cmd

            return fn

    def usage(self, cmd=None, scriptname=None, exception=None, file=sys.stdout):
        if exception is not None:
            scriptname, cmd = exception.scriptname, exception.cmd

        if scriptname is None:
            scriptname = sys.argv[0]

        if cmd is None:
            self.print_top_help(scriptname, file=file)
        else:
            if isinstance(cmd, str):
                cmd = self.commands[cmd]

            self.print_command_help(scriptname, cmd, file=file)

    def openinput(self, filein):
        if filein == '-':
            return sys.stdin
        ext = os.path.splitext(filein)[1]
        if ext in ['.gz', '.GZ']:
            return gzip.open(filein, 'rb')
        if ext in ['.bz', '.bz2']:
            return bz2.BZ2File(filein, 'rb')
        return open(filein, 'rb')

    def writeconfig(self, iniconffile=sys.argv[0] + ".ini"):
        """
        OVERWRITE an ini style config file that holds all of the default
        command line options.

        :param iniconffile: the file name of the ini file, defaults to
                            '{scriptname}.ini'.
        """
        fp = open(iniconffile, "w")
        for cmdname in self.commands:
            cmd = self.commands[cmdname]
            self.write(fp, os.linesep)
            self.write(fp, "[%s]%s" % (cmdname, os.linesep))
            for line in self.return_cmd_doc(cmd):
                self.write(fp, "# " + line + os.linesep)
            for line in self.return_argnames_doc(cmd):
                self.write(fp, "# " + line + os.linesep)
            for key in cmd.keywords:
                head = self.return_head(cmd, key)
                for line in self.return_individual_keyword_doc(cmd, key, head):
                    self.write(fp, "# " + line + os.linesep)
                self.write(fp, "%s = %s%s" % (key, cmd.keywords[key],
                                              os.linesep))
                self.write(fp, os.linesep)
        fp.close()

    def write(self, file, content):
        # This function automatically converts strings to bytes
        # if running under Python 3. Otherwise we cannot write
        # to a file.

        if sys.version_info[:2] >= (3, 0):
            content = bytes(content, 'utf-8')
        try:
            file.write(content)
        except TypeError:
            # With some file content's type must be str, not bytes
            file.write(str(content))

    def print_top_help(self, scriptname, file=sys.stdout):
        """Prints the documentation for the script and exits.

        :param scriptname: the name of the script being executed (argv[0]).
        :param file: the file to write the help to. The default is stdout.
        """
        # Print the basic help for running a command
        self.write(file, "\nUsage: %s COMMAND <options>\n\n" % scriptname)

        # Get a sorted list of all command names
        cmdnames = sorted(self.commands.keys())
        if cmdnames:
            # Calculate the indent for the doc strings by taking the longest
            # command name and adding 3 (one space before the name and two
            # after)
            rindent = max(len(name) for name in cmdnames) + 3

            self.write(file, "Available commands:\n")
            for cmdname in cmdnames:
                # Get the Cmd object for this command
                cmd = self.commands[cmdname]

                # Calculate the padding necessary to fill from the end of the
                # command name to the documentation margin
                tab = " " * (rindent - len(cmdname) - 1)
                self.write(file, " " + cmdname + tab)

                # Get the paragraphs of the command's docstring
                paras = process_docstring(cmd.docstring)
                if paras:
                    # Print the first paragraph
                    self.write(file, "\n".join(format_paras([paras[0]], 76,
                                             indent=rindent, lstripline=[0])))
                    self.write(file, "\n")
                else:
                    self.write(file, "\n")

        self.write(file, "\n")
        self.write(file, "Use '%s <command> --help' for individual command "
                   "help.\n" % scriptname)

    def return_cmd_doc(self, cmd):
        # Print the documentation for this command
        paras = process_docstring(cmd.docstring)
        ret = []
        if paras:
            # Print the first paragraph with no indent (usually just a summary
            # line)
            for line in format_paras([paras[0]], 76):
                ret.append(line)

            # Print subsequent paragraphs indented by 4 spaces
            if len(paras) > 1:
                ret.append("")
                for line in format_paras(paras[1:], 76, indent=4):
                    ret.append(line)
            ret.append("")
        return ret

    def return_argnames_doc(self, cmd):
        # Return documentation for required arguments
        ret = []
        posargs = [a for a in cmd.argnames if a not in cmd.keywords]
        if posargs:
            ret.append("")
            ret.append("Required Arguments:")
            ret.append("")

            # Find the length of the longest formatted heading
            rindent = max(len(argname) + 3 for argname in posargs)
            # Pad the headings so they're all as long as the longest one
            heads = [(head, head.ljust(rindent)) for head in posargs]

            # Print the arg docs
            for keyname, head in heads:
                ret += self.return_individual_keyword_doc(cmd, keyname, head,
                                                          rindent=rindent)
        ret.append("")
        return ret

    def return_individual_keyword_doc(self, cmd, keyname, head, rindent=None):
        # Return documentation for optional arguments
        ret = []
        if rindent is None:
            rindent = len(head) + 2
        if keyname in cmd.paramdocs:
            paras = process_docstring(cmd.paramdocs.get(keyname, ""))
            formatted = format_paras(paras, 76, indent=rindent, lstripline=[0])
            ret.append("  " + head + formatted[0])
            for line in formatted[1:]:
                ret.append("  " + line)
        else:
            ret.append("  " + head)
        return ret

    def return_head(self, cmd, keyname):
        head = keyname
        head = " --" + head
        if keyname in cmd.shortopts:
            head = " -" + cmd.shortopts[keyname] + head
        head += "  "
        return head

    def return_keyword_doc(self, cmd):
        # Return documentation for optional arguments
        ret = []
        if cmd.keywords:
            ret.append("")
            ret.append("Options:")
            ret.append("")

            # Get a list of keyword argument names
            keynames = cmd.keywords.keys()

            # Make formatted headings, e.g. " -k --keyword  ", and put them in
            # a list like [(name, heading), ...]
            heads = []
            for keyname in keynames:
                head = self.return_head(cmd, keyname)
                heads.append((keyname, head))

            if heads:
                # Find the length of the longest formatted heading
                rindent = max(len(head) + 2 for keyname, head in heads)
                # Pad the headings so they're all as long as the longest one
                heads = [(keyname, head + (" " * (rindent - len(head) - 2)))
                         for keyname, head in heads]

                # Print the option docs
                for keyname, head in heads:
                    ret += self.return_individual_keyword_doc(cmd, keyname,
                                                              head, rindent)

            ret.append("")

            if any((cmd.keywords.get(a) is None) for a in cmd.argnames):
                ret.append("(specifying a double hyphen (--) in the argument"
                           " list means all")
                ret.append("subsequent arguments are treated as bare "
                           "arguments, not options)")
                ret.append("")
        return ret

    def print_command_help(self, scriptname, cmd, file=sys.stdout):
        """Prints the documentation for a specific command and exits.

        :param scriptname: the name of the script being executed (argv[0]).
        :param cmd: the Cmd object representing the command.
        :param file: the file to write the help to. The default is stdout.
        """

        # Print the usage for the command
        self.write(file, "\nUsage: %s %s" % (scriptname, cmd.name))

        # Print the required and "optional" arguments (where optional
        # arguments are keyword arguments with default None).
        for name in cmd.argnames:
            if name not in cmd.keywords:
                # This is a positional argument
                self.write(file, " <%s>" % name)
            else:
                # This is a keyword/optional argument
                self.write(file, " [<%s>]" % name)

        if cmd.has_varargs:
            # This command accepts a variable number of positional arguments
            self.write(file, " [...]")
        self.write(file, "\n\n")

        self.write(file, "\n".join(self.return_cmd_doc(cmd)))
        self.write(file, "\n".join(self.return_argnames_doc(cmd)))
        self.write(file, "\n".join(self.return_keyword_doc(cmd)))

    def parse_args(self, scriptname, cmd, argv, test=False):
        keywords = cmd.keywords
        shortopts = cmd.shortopts

        def type_error(name, value, t):
            if not test:
                msg = "%s value %r must be %s" % (name, value, t)
                raise CommandError(msg, scriptname, cmd)

        # shortopts maps long option names to characters. To look up short
        # options, we need to create a reverse mapping.
        shortchars = dict((v, k) for k, v in shortopts.items())

        # The *vargs list and **kwargs dict to build up from the command line
        # arguments
        vargs = []
        kwargs = {}

        doubledashcnt = 0
        singledashcnt = 0
        while argv:
            # Take the next argument
            arg = argv.pop(0)

            if arg == "--":
                doubledashcnt = doubledashcnt + 1
                assert doubledashcnt == 1
                # All arguments following a single hyphen are treated as
                # positional arguments
                vargs.extend(argv)
                break

            elif arg == "-":
                # sys.stdin
                singledashcnt = singledashcnt + 1
                assert singledashcnt == 1
                vargs.append('-')

            elif arg.startswith("--"):
                # Process long option

                value = None
                if "=" in arg:
                    # The argument was specified like --keyword=value
                    name, value = arg[2:].split("=", 1)
                    # strip quotes if value is quoted like
                    # --keyword='multiple words'
                    value = value.strip('\'"')

                    default = keywords.get(name)
                    try:
                        value = totype(value, default)
                    except (TypeError, ValueError):
                        type_error(name, value, type(default))
                else:
                    # The argument was not specified with an equals sign...
                    name = arg[2:]
                    default = keywords.get(name)

                    if type(default) is bool:
                        # If this option is a boolean, it doesn't need a value;
                        # specifying it on the command line means "do the
                        # opposite of the default".
                        value = not default
                    else:
                        # The next item in the argument list is the value, i.e.
                        # --keyword value
                        if not argv or argv[0].startswith("-"):
                            # Oops, there isn't a value available... just use
                            # True, assuming this is a flag.
                            value = True
                        else:
                            value = argv.pop(0)

                        try:
                            value = totype(value, default)
                        except (TypeError, ValueError):
                            type_error(name, value, type(default))

                # Store this option
                kwargs[name] = value

            elif arg.startswith("-") and cmd.shortopts:
                # Process short option(s)

                # For each character after the '-'...
                for i in range(1, len(arg)):
                    char = arg[i]
                    if char not in shortchars:
                        continue

                    # Get the long option name corresponding to this char
                    name = shortchars[char]

                    default = keywords[name]
                    if type(default) is bool:
                        # If this option is a boolean, it doesn't need a value;
                        # specifying it on the command line means "do the
                        # opposite of the default".
                        kwargs[name] = not default
                    else:
                        # This option requires a value...
                        if i == len(arg) - 1:
                            # This is the last character in the list, so the
                            # next argument on the command line is the value.
                            value = argv.pop(0)
                        else:
                            # There are other characters after this one, so
                            # the rest of the characters must represent the
                            # value (i.e. old-style UNIX option like -Nname)
                            value = arg[i + 1:]

                        try:
                            kwargs[name] = totype(value, default)
                        except (TypeError, ValueError):
                            type_error(name, value, type(default))
                        break
            else:
                # This doesn't start with "-", so just add it to the list of
                # positional arguments.
                vargs.append(arg)

        return vargs, kwargs

    def parse(self, argv=None, test=False):
        """Parses the command and parameters to call from the list of command
        line arguments. Returns a tuple of (scriptname string, Cmd object,
        position arg list, keyword arg dict).

        This method will raise TopHelp if the parser finds that the user
        requested the overall script help, and raise CommandHelp if the user
        requested help on a specific command.

        :param argv: the list of options passed to the command line (sys.argv).
        """

        if argv is None:
            argv = sys.argv

        scriptname = argv[0]

        if len(argv) < 2 and self.defaultcommand:
            argv.append(self.defaultcommand.name)

        if (len(argv) < 2) or (argv[1] == "-h" or argv[1] == "--help"):
            # Print the documentation for the script
            raise TopHelp(scriptname)

        if argv[1] == "help":
            if len(argv) > 2 and argv[2] in self.commands:
                cmd = self.commands[argv[2]]
                raise CommandHelp(scriptname, cmd)
            raise TopHelp(scriptname)

        if len(argv) > 1 and argv[1] in self.commands:
            # The first argument on the command line (after the script name
            # is the command to run.
            cmd = self.commands[argv[1]]

            if len(argv) > 2 and (argv[2] == "-h" or argv[2] == "--help"):
                raise CommandHelp(scriptname, cmd)

            options = argv[2:]
        else:
            # No known command was specified. If there's a default command,
            # use that.
            cmd = self.defaultcommand
            if cmd is None:
                raise CommandError("No command specified", scriptname)

            options = argv[1:]

        # Parse the rest of the arguments on the command line and use them to
        # call the command function.
        args, kwargs = self.parse_args(scriptname, cmd, options, test=test)
        return (scriptname, cmd, args, kwargs)

    def apply(self, scriptname, cmd, args, kwargs, instance=None):
        """Calls the command function.
        """

        # Create a list of positional arguments: arguments that are either
        # required (not in keywords), or where the default is None (taken to be
        # an optional positional argument). This is different from the Python
        # calling convention, which will fill in keyword arguments with extra
        # positional arguments.

        # Rearrange the arguments into the order Python expects
        newargs = []
        newkwargs = kwargs.copy()
        for name in cmd.argnames:
            if name in cmd.keywords:
                if not args:
                    break
                # keyword arg
                if cmd.has_varargs:
                    # keyword params are not replaced by bare args if the func
                    # also has varags but they must be specified as positional
                    # args for proper processing of varargs
                    value = cmd.keywords[name]
                    if name in newkwargs:
                        value = newkwargs[name]
                        del newkwargs[name]
                    newargs.append(value)
                elif not name in newkwargs:
                    newkwargs[name] = args.pop(0)

            else:
                # positional arg
                if name in newkwargs:
                    newargs.append(newkwargs[name])
                    del newkwargs[name]
                else:
                    if args:
                        newargs.append(args.pop(0))
                    else:
                        # This argument is required but we don't have a bare
                        # arg to fill it
                        msg = "Required argument %r not given"
                        raise CommandError(msg % (name), scriptname, cmd)
        if args:
            if cmd.has_varargs:
                newargs.extend(args)
            else:
                msg = "Too many arguments to %s: %s"
                raise CommandError(msg % (cmd.name, " ".join(args)),
                                   scriptname, cmd)

        if not cmd.has_kwargs:
            for k in newkwargs:
                if k not in cmd.keywords:
                    raise CommandError("Unknown option --%s" % k,
                                       scriptname, cmd)

        if cmd.is_method and instance is not None:
            return cmd.fn(instance, *newargs, **newkwargs)
        return cmd.fn(*newargs, **newkwargs)

    def run(self, argv=None, main=True, help_on_error=False,
            outfile=sys.stdout, errorfile=sys.stderr, helpfile=sys.stdout,
            errorcode=1, instance=None):
        """Takes a list of command line arguments, parses it into a command
        name and options, and calls the function corresponding to the command
        with the given arguments.

        :param argv: the list of options passed to the command line (sys.argv).
        :param main: if True, print error messages and exit instead of
            raising an exception.
        :param help_on_error: if True, when an error occurs, print the usage
            help after the error.
        :param errorfile: the file to write error messages to.
        :param helpfile: the file to write usage help to.
        :param errorcode: the exit code to use when calling sys.exit() in the
            case of an error. If this is 0, sys.exit() will not be called.
        """

        try:
            value = self.apply(*self.parse(argv), instance=instance)
            if main and value is not None:
                self.write(outfile, str(value) + '\n')
            return value
        except TopHelp as e:
            if not main:
                raise
            self.usage(scriptname=e.scriptname, file=helpfile)
        except CommandHelp as e:
            if not main:
                raise
            self.usage(e.cmd, scriptname=e.scriptname, file=helpfile)
        except CommandError as e:
            if not main:
                raise
            self.write(errorfile, str(e) + "\n")
            if help_on_error:
                self.write(errorfile, "\n")
                self.usage(e.cmd, scriptname=e.scriptname, file=helpfile)
            if errorcode:
                sys.exit(errorcode)

    def test(self, argv=None, file=sys.stdout):
        """Takes a list of command line arguments, parses it into a command
        name and options, and prints what the resulting function call would
        look like. This may be useful for testing how command line arguments
        would be passed to your functions.

        :param argv: the list of options passed to the command line (sys.argv).
        :param file: the file to write result to.
        """

        try:
            script, cmd, args, kwargs = self.parse(argv, test=True)
            result = "%s(%s" % (cmd.name, ", ".join(repr(a) for a in args))
            if kwargs:
                kws = ", ".join("%s=%r" % (k, v) for k, v in kwargs.items())
                result += ", " + kws
            result += ")"
            self.write(file, result)
            return result  # useful for testing
        except TopHelp:
            self.write(file, "(top-level help)")
        except CommandHelp as e:
            self.write(file, "(help for %s command)" % e.cmd.name)


_baker = Baker()
command = _baker.command
run = _baker.run
test = _baker.test
usage = _baker.usage
writeconfig = _baker.writeconfig
openinput = _baker.openinput
