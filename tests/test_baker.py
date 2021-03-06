import os
import sys
import bz2
import gzip
import shutil
import tempfile
import unittest
try:
    from cStringIO import StringIO
except ImportError:  # pragma: no cover
    from io import BytesIO as StringIO

import baker


MAIN_HELP = """Usage: script.py COMMAND <options>

Available commands:
 main
 open  Open a URL.

Use 'script.py <command> --help' for individual command help.
"""

COMMAND_HELP = """Usage: script.py open <url> [<xml>] [<json>] [<use>]

Open a URL.

Required Arguments:

  url   url to open.

Options:

   --xml   use it if you want an xml output.
   --json  use it if you want a json output.
   --use

(specifying a double hyphen (--) in the argument list means all
subsequent arguments are treated as bare arguments, not options)
"""

INPUT_TEST = """This is a test.

Testing.
"""

INI_SAMPLE = """[main]
#
#    --port
port = 8888

#    --auth
auth = False

[open]
# Open a URL.
#
#
# Required Arguments:
#
#   url   url to open.
#
#    --xml  use it if you want an xml output.
xml = False

#    --json  use it if you want a json output.
json = False

#    --use
use = True
"""

VARARGS_HELP = """Usage: script.py test [<files>...]

Command documentation.

Variable arguments:

   *files   Varargs documentation.
"""


def build_baker():
    b = baker.Baker()

    @b.command(default=True)
    def main(auth=False, port=8888):
        return auth, port

    @b.command
    def open(url, xml=False, json=False, use=True):
        """
        Open a URL.

        :param url: url to open.
        :param xml: use it if you want an xml output.
        :param json: use it if you want a json output.
        """
        return url, xml, json, use

    return b


class TestFunctions(unittest.TestCase):

    def test_totype(self):
        """Test whether totype works"""
        candidates = {("true", "yes", "on", "1"): True,
                      ("false", "no", "off", "0"): False}
        for values, expected in candidates.items():
            for value in values:
                self.assertEqual(baker.totype(value, True), expected)
                self.assertEqual(baker.totype(value, False), expected)
        self.assertEqual(baker.totype("1", 42), 1)
        self.assertEqual(baker.totype("1", 0.0), 1.0)
        self.assertEqual(baker.totype("1", baker.Baker()), "1")
        self.assertRaises(TypeError, baker.totype, "invalid", False)

    def test_docstrings(self):
        """Test docstring processing"""
        docstring = """This is an example docstring.

        :param add: Add a line.
        :param remove: Remove a line.
        :param more_complicated: A little more complicated.
            This is not just a test of indents.

            but also how Baker handles blank lines.
        :param yetanother: To make sure the regex is correct.
        """
        self.maxDiff = None
        self.assertEqual(baker.find_param_docs(docstring),
                         {"add": "Add a line.\n",
                          "remove": "Remove a line.\n",
                          "more_complicated": "A little more complicated.\n            This is not just a test of indents.\n\n            but also how Baker handles blank lines.\n",
                          "yetanother": "To make sure the regex is correct.\n"})
        self.assertEqual(baker.remove_param_docs(docstring),
                         "This is an example docstring.\n\n" + " " * 8)
        self.assertEqual(baker.process_docstring(docstring),
                         ["This is an example docstring.",
                          ":param add: Add a line. "
                          ":param remove: Remove a line. "
                          ":param more_complicated: A little more complicated. This is not just a test of indents.",
                          "but also how Baker handles blank lines. "
                          ":param yetanother: To make sure the regex is correct."])

    def test_openinput(self):
        """Test Baker.openinput()"""
        self.assertTrue(baker.openinput('-') is sys.stdin)
        tempdir = tempfile.mkdtemp()
        for ext, opener in [(".gz", gzip.GzipFile), (".bz2", bz2.BZ2File)]:
            g = os.path.join(tempdir, "test" + ext)
            input = TestBaker.bytes(INPUT_TEST, 'utf-8')
            fobj = opener(g, "w")
            fobj.write(input)
            fobj.close()
            self.assertEqual(baker.openinput(g).read(), input)


class TestBaker(unittest.TestCase):

    @staticmethod
    def bytes(string, encoding):
        if sys.version_info[:2] >= (3, 0):  # pragma: no cover
            return bytes(string, encoding)
        return string

    def assertEqual(self, a, b):
        # this is for Python 3 compatibility
        if sys.version_info[:2] >= (3, 0):  # pragma: no cover
            if isinstance(a, bytes) and not isinstance(b, bytes):
                b = self.bytes(b, 'utf-8')
        super(TestBaker, self).assertEqual(a, b)

    def test_simple(self):
        """Test a very simple Baker"""
        b = baker.Baker()

        @b.command
        def test(a, b, c):
            return (a, b, c)
        self.assertEqual(b.run(["s", "test", "1", "2", "3"], main=False),
                         ("1", "2", "3"))

    def test_method(self):
        """Test whether Baker.command works on methods too"""
        b = baker.Baker()

        class Test(object):

            def __init__(self, start):
                self.start = start

            @b.command
            def test(self, a, b, cmd=False):
                return self.start, a, b, cmd

        test = Test(42)
        self.assertEqual(b.run(["s", "test", "1", "2", "--cmd"],
                               instance=test),
                         (42, "1", "2", True))

    def test_default(self):
        """Test default commands"""
        b = baker.Baker()

        @b.command(default=True)
        def test(a="a", b="b", c="c"):
            return (a, b, c)

        self.assertEqual(b.run(["s", "1", "2", "3"], main=False),
                         ("1", "2", "3"))
        self.assertEqual(b.run(["s"], main=False), ("a", "b", "c"))

    def test_options(self):
        """Test options"""
        b = baker.Baker()

        @b.command
        def test(a="a", b="b", c="c"):
            return (a, b, c)

        self.assertEqual(b.run(["s", "test", "-a", "alfa", "-b=bravo"],
                               main=False),
                         ("alfa", "bravo", "c"))
        self.assertEqual(b.run(["s", "test", "alfa", "bravo"], main=False),
                         ("alfa", "bravo", "c"))
        self.assertEqual(b.run(["s", "test", "-b", "bravo", "alfa"],
                               main=False),
                         ("alfa", "bravo", "c"))
        self.assertEqual(b.run(["s", "test", "-a", "alfa",
                                "-b='multiple words'"], main=False),
                         ("alfa", "multiple words", "c"))

    def test_shortopts(self):
        """Test short options"""
        b = baker.Baker()

        @b.command(shortopts={"alfa": "a", "bravo": "b", "charlie": "c"})
        def test(alfa="1", bravo="2", charlie=False):
            return (alfa, bravo, charlie)

        self.assertEqual(b.run(["s", "test", "-a", "100", "-cb200"],
                               main=False),
                         ("100", "200", True))

    def test_optional(self):
        """Test optional arguments"""
        b = baker.Baker()

        @b.command
        def test(a, b=False, c=None):
            return (a, b, c)

        self.assertEqual(b.run(["s", "test", "100"], main=False),
                         ("100", False, None))
        self.assertEqual(b.run(["s", "test", "100", "200"], main=False),
                         ("100", "200", None))
        self.assertEqual(b.run(["s", "test", "-b", "100", "200"], main=False),
                         ("100", True, "200"))

    def test_kwargs(self):
        """Test **kwargs"""
        b = baker.Baker()

        @b.command
        def test(**kwargs):
            return kwargs

        self.assertEqual(b.run(["s", "test", "-a", "1", "-b", "2"],
                               main=False),
                         {"a": "1", "b": "2"})

    def test_defaulted_args_and_kwargs(self):
        """Test *args and **kwargs with default arguments"""
        b = baker.Baker()

        @b.command
        def test(a=0, **kwargs):
            return (a, kwargs)

        self.assertEqual(b.run(["s", "test", "-a", "1", "-b", "2"],
                               main=False),
                         (1, {"b": "2"}))
        self.assertEqual(b.run(["s", "test", "-b", "1", "-c", "2"],
                               main=False),
                         (0, {"b": "1", "c": "2"}))

    def test_args(self):
        """Test *args"""
        b = baker.Baker()

        @b.command
        def test(*args):
            return args

        self.assertEqual(b.run(["s", "test", "1", "2"], main=False),
                        ("1", "2"))

    def test_defaulted_arg_and_args(self):
        """Test *args and arguments with default values"""
        b = baker.Baker()

        @b.command
        def test(a="0", *args):
            return (a, args)

        self.assertEqual(b.run(["s", "test", "1", "2"], main=False),
                        ("0", ("1", "2")))
        self.assertEqual(b.run(["s", "test", "-a", "1", "2"], main=False),
                        ("1", ("2",)))
        # This one should assign the named arg first
        self.assertEqual(b.run(["s", "test", "2", "-a", "1"], main=False),
                        ("1", ("2",)))

    def test_pos_defaulted_arg_and_args(self):
        """Test positional arguments, arguments with default values
        and *args
        """
        b = baker.Baker()

        @b.command
        def test(a, b="0", *args):
            return (a, b, args)

        self.assertEqual(b.run(["s", "test", "1", "-b", "2"], main=False),
                        ("1", "2", ()))
        self.assertEqual(b.run(["s", "test", "1", "-b", "2"], main=False),
                        ("1", "2", ()))
        self.assertEqual(b.run(["s", "test", "2", "1"], main=False),
                        ("2", "0", ("1",)))
        self.assertEqual(b.run(["s", "test", "1", "2", "3"], main=False),
                        ("1", "0", ("2", "3",)))

        ce = baker.CommandError
        br = b.run

        self.assertRaises(ce, br, ["s", "test", "-b", "1", "--c", "2"],
                          main=False)
        self.assertRaises(ce, br, ["s", "test", "1", "--c", "2"],
                          main=False)

    def test_pos_defaulted_arg_and_kwargs_2(self):
        """Test positional arguments, arguments with default values and
        **kwargs
        """
        b = baker.Baker()

        @b.command
        def test(a, b="0", **kwargs):
            return (a, b, kwargs)

        self.assertEqual(b.run(["s", "test", "1", "-b", "2"], main=False),
                        ("1", "2", {}))
        self.assertEqual(b.run(["s", "test", "1", "-b", "2", "-c", "3"],
                               main=False),
                        ("1", "2", {"c": "3"}))

        ce = baker.CommandError
        br = b.run

        self.assertRaises(ce, br, ["s", "test", "-b", "1", "-c", "2"],
                          main=False)

    def test_pos_defaulted_arg_args_and_kwargs(self):
        """Test positional arguments, arguments with default values, *args
        and **kwargs
        """
        b = baker.Baker()

        @b.command
        def test(a, b="0", *args, **kwargs):
            return (a, b, args, kwargs)

        self.assertEqual(b.run(["s", "test", "1", "-b", "2"], main=False),
                        ("1", "2", (), {}))
        self.assertEqual(b.run(["s", "test", "1", "-b", "2"], main=False),
                        ("1", "2", (), {}))
        self.assertEqual(b.run(["s", "test", "2", "1"], main=False),
                        ("2", "0", ("1",), {}))
        self.assertEqual(b.run(["s", "test", "1", "2", "3"], main=False),
                        ("1", "0", ("2", "3",), {}))
        self.assertEqual(b.run(["s", "test", "1", "--c", "2"], main=False),
                        ("1", "0", (), {"c": "2"}))

        ce = baker.CommandError
        br = b.run
        self.assertRaises(ce, br, ["s", "test", "-b", "1", "--c", "2"],
                          main=False)

    def test_boolean_arg_and_args(self):
        """Test boolean arguments and *args"""
        b = baker.Baker()

        @b.command
        def test(a=False, *args):
            return (a, args)

        self.assertEqual(b.run(["s", "test", "1", "2"], main=False),
                        (False, ("1", "2")))
        self.assertEqual(b.run(["s", "test", "-a", "1", "2"], main=False),
                        (True, ("1", "2")))

    def test_noargs(self):
        """Test with a function accepting no arguments"""
        b = baker.Baker()

        @b.command
        def noargs():
            return 123

        self.assertEqual(b.run(["script.py", "noargs"], main=False), 123)

    def test_alias(self):
        """Test command alias"""
        b = baker.Baker()

        @b.command(name="track-all")
        def trackall(workaround=None):
            return 123

        self.assertEqual(b.run(["script.py", "track-all"], main=False), 123)

        ce = baker.CommandError
        br = b.run
        self.assertRaises(ce, br, ["s", "trackall"], main=False)

    def test_single_dash(self):
        """Test single dash (input from stdin)"""
        b = baker.Baker()

        @b.command
        def test(a, b=0):
            return a, b

        self.assertEqual(b.run(["s", "test", "first"], main=False),
                         ("first", 0))
        self.assertEqual(b.run(["s", "test", "-b", "4", "first"],
                               main=False),
                         ("first", 4))

    def test_double_dash(self):
        """Test double dash (--)"""
        b = baker.Baker()

        @b.command
        def test(a, b=0, c=4):
            return a, b, c

        self.assertEqual(b.run(["s", "test", "-b", "7", "--", "6", "8"],
                               main=False),
                         ("6", 7, "8"))
        self.assertRaises(baker.CommandError, b.run,
                          ["s", "test", "9", "--", "10", "--", "9"],
                          main=False)

    def test_global_command(self):
        """Test whether global command works as expected"""
        b = baker.Baker()
        self.assertEqual(b.global_options, {})

        @b.command(global_command=True)
        def global_matcher(n=5, val=True, index="http://pypi.python.org/pypi"):
            n = int(n)
            if n > 40:
                n = -1
            return {"num": n, "val": val, "index": index}

        @b.command
        def test(req, bolly=False):
            return req, bolly

        @b.command
        def second(a, b=0):
            return a, b

        default_global_options = {"n": 5, "val": True,
                                  "index": "http://pypi.python.org/pypi"}
        self.assertEqual(b.global_options, default_global_options)
        self.assertEqual(b.run(["s", "test", "rio", "--bolly"], main=False),
                         ("rio", True))
        self.assertEqual(b.global_options, default_global_options)
        self.assertEqual(b.run(["s", "second", "9"], main=False), ("9", 0))
        self.assertEqual(b.global_options, default_global_options)
        self.assertEqual(b.run(["s", "-n", "2", "--val", "--index", "short",
                                "test", "pos"], main=False),
                         ("pos", False))
        self.assertEqual(b.global_options, {"num": 2, "val": False, "index":
                                            "short"})
        # Make sure that the real command is found even when the previous one
        # starts with dashes (-- or -). This happens when the previous option
        # is a boolean one.
        self.assertEqual(b.run(["s", "-n", "45", "--val", "test", "pos"],
                               main=False),
                         ("pos", False))
        self.assertEqual(b.global_options, {"num": -1, "val": False, "index":
                                            "http://pypi.python.org/pypi"})

    def test_global_options_get(self):
        b = baker.Baker()
        self.assertEqual(b.get('a', 5), 5)
        self.assertEqual(b.get('a'), None)
        b.global_options = {'a': 2, 'b': 3}
        self.assertEqual(b.get('a'), 2)
        self.assertEqual(b.get('b', False), 3)
        self.assertEqual(b.get('c'), None)

    def test_global_command_error(self):
        """Test whether global command raises errors as expected"""
        def create_bad_global_command():
            b = baker.Baker()

            @b.command(global_command=True)
            def test(a, b, key='val'):
                pass

        def create_global(b):
            @b.command(global_command=True)
            def test(a=1, b=2):
                pass

        def create_default(b):
            @b.command(default=True)
            def second(a, b, c=24):
                pass

        def create_both1():
            b = baker.Baker()
            create_global(b)
            create_default(b)

        def create_both2():
            b = baker.Baker()
            create_default(b)
            create_global(b)


        ce = baker.CommandError
        self.assertRaises(ce, create_bad_global_command)
        self.assertRaises(ce, create_both1)
        self.assertRaises(ce, create_both2)

    def test_nooptional(self):
        """Test with a function accepting only positional arguments"""
        b = baker.Baker()

        @b.command
        def test(a, b, c):
            return a, b, c

        self.assertEqual(b.run(["script.py", "test", "1", "2", "3"],
                               main=False), ('1', '2', '3'))

    def test_test(self):
        """Test 'test' mode"""
        b = baker.Baker()

        @b.command
        def test(a, b):
            return a, b

        self.assertEqual(b.test(["s", "test", "1", "2"]), "test('1', '2')")

    def test_usage(self):
        """Test usage output"""
        b = baker.Baker()

        @b.command
        def test():
            "Test command"
            pass

        f = StringIO()
        b.usage("test", scriptname="script.py", fobj=f)
        self.assertEqual(f.getvalue(),
                         'Usage: script.py test\n\nTest command\n')

    def test_varargs_usage(self):
        """Test usage output when *args is used"""
        b = baker.Baker()

        @b.command
        def test(*files):
            """Command documentation.

            :param files: Varargs documentation.
            """

            return files

        out = StringIO()
        b.run(["script.py", "test", "--help"], helpfile=out)
        self.assertEqual(out.getvalue(), VARARGS_HELP)

    def test_help(self):
        """Test program help"""
        b = build_baker()
        out = StringIO()
        b.run(["script.py", "--help"], helpfile=out)
        self.assertEqual(out.getvalue(), MAIN_HELP)
        out = StringIO()
        b.run(["script.py", "open", "--help"], helpfile=out)
        self.assertEqual(out.getvalue(), COMMAND_HELP)

    def test_writeconfig(self):
        """Test Baker.writeconfig()"""
        b = build_baker()
        tempdir = tempfile.mkdtemp()
        ini = os.path.join(tempdir, "conf.ini")
        b.writeconfig(ini)
        with open(ini) as fobj:
            self.assertEqual(fobj.read(), INI_SAMPLE)
        shutil.rmtree(tempdir)

    def test_errors(self):
        """Test various errors"""
        b = baker.Baker()

        @b.command
        def test(times=10):
            return True

        @b.command
        def foo(reqd):
            return True

        ce = baker.CommandError
        br = b.run

        self.assertRaises(baker.TopHelp, b.run, ["s"], main=False)
        self.assertRaises(ce, br, ["s", "blah"], main=False)
        self.assertRaises(ce, br, ["s", "test", "--blah"], main=False)
        self.assertRaises(ce, br, ["s", "test", "--times", "bar"], main=False)
        self.assertRaises(ce, br, ["s", "test", "1", "2", "3"], main=False)
        self.assertRaises(ce, br, ["s", "foo"], main=False)


if __name__ == "__main__":
    unittest.main()
