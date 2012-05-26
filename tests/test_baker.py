import os
import sys
import bz2
import gzip
import shutil
import tempfile
import unittest
try:
    from cStringIO import StringIO
except ImportError:  # python 3
    from io import BytesIO as StringIO

import baker


MAIN_HELP = """
Usage: script.py COMMAND <options>

Available commands:
 main  
 open  Open a URL.

Use 'script.py <command> --help' for individual command help.
"""

COMMAND_HELP = """
Usage: script.py open <url> [<xml>] [<json>] [<use>]

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
        docstring = """This is an example docstring.

        :param add: Add a line.
        :param remove: Remove a line.
        """

        self.assertEqual(baker.find_param_docs(docstring),
                         {"add": "Add a line.\n",
                          "remove": "Remove a line.\n"})
        self.assertEqual(baker.remove_param_docs(docstring),
                         "This is an example docstring.\n\n" + " " * 8)
        self.assertEqual(baker.process_docstring(docstring),
                         ["This is an example docstring.",
                          ":param add: Add a line. " \
                          ":param remove: Remove a line."])


class TestBaker(unittest.TestCase):

    def bytes(self, string, encoding):
        if sys.version_info[:2] >= (3, 0):
            return bytes(string, encoding)
        return string

    def assertEqual(self, a, b):
        if sys.version_info[:2] >= (3, 0):
            if isinstance(a, bytes) and not isinstance(b, bytes):
                b = self.bytes(b, 'utf-8')
        super(TestBaker, self).assertEqual(a, b)

    def test_simple(self):
        b = baker.Baker()

        @b.command
        def test(a, b, c):
            return (a, b, c)
        self.assertEqual(b.run(["s", "test", "1", "2", "3"], main=False),
                         ("1", "2", "3"))

    def test_method(self):
        b = baker.Baker()

        class Test(object):

            def __init__(self, start):
                self.start = start

            @b.command
            def test(self, a, b, cmd=False):
                return self.start, a, b, cmd

        test = Test(42)
        self.assertEqual(b.run(["s", "test", "1", "2", "--cmd"], instance=test),
                         (42, "1", "2", True))

    def test_default(self):
        b = baker.Baker()

        @b.command(default=True)
        def test(a="a", b="b", c="c"):
            return (a, b, c)
        self.assertEqual(b.run(["s", "1", "2", "3"], main=False),
                         ("1", "2", "3"))
        self.assertEqual(b.run(["s"], main=False), ("a", "b", "c"))

    def test_options(self):
        b = baker.Baker()

        @b.command
        def test(a="a", b="b", c="c"):
            return (a, b, c)
        self.assertEqual(b.run(["s", "test", "--a", "alfa", "--b=bravo"],
                               main=False),
                         ("alfa", "bravo", "c"))

    def test_shortopts(self):
        b = baker.Baker()

        @b.command(shortopts={"alfa": "a", "bravo": "b", "charlie": "c"})
        def test(alfa="1", bravo="2", charlie=False):
            return (alfa, bravo, charlie)
        self.assertEqual(b.run(["s", "test", "-a", "100", "-cb200"],
                               main=False),
                         ("100", "200", True))

    def test_optional(self):
        b = baker.Baker()

        @b.command
        def test(a, b=False, c=None):
            return (a, b, c)

        self.assertEqual(b.run(["s", "test", "100"], main=False),
                         ("100", False, None))
        self.assertEqual(b.run(["s", "test", "100", "200"], main=False),
                         ("100", "200", None))
        self.assertEqual(b.run(["s", "test", "--b", "100", "200"], main=False),
                         ("100", True, "200"))

    def test_kwargs(self):
        b = baker.Baker()

        @b.command
        def test(**kwargs):
            return kwargs

        self.assertEqual(b.run(["s", "test", "--a", "1", "--b", "2"],
                               main=False),
                         {"a": "1", "b": "2"})

    def test_noargs(self):
        b = baker.Baker()

        @b.command
        def noargs():
            return 123

        self.assertEqual(b.run(["script.py", "noargs"], main=False), 123)

    def test_alias(self):
        b = baker.Baker()

        @b.command(name="track-all")
        def trackall(workaround=None):
            return 123

        self.assertEqual(b.run(["script.py", "track-all"], main=False), 123)

    def test_nooptional(self):
        b = baker.Baker()

        @b.command
        def test(a, b, c):
            return a, b, c

        self.assertEqual(b.run(["script.py", "test", "1", "2", "3"],
                               main=False), ('1', '2', '3'))

    def test_test(self):
        b = baker.Baker()

        @b.command
        def test(a, b):
            return a, b

        self.assertEqual(b.test(["s", "test", "1", "2"]), "test('1', '2')")

    def test_usage(self):
        b = baker.Baker()

        @b.command
        def test():
            "Test command"
            pass

        f = StringIO()
        b.usage("test", scriptname="script.py", file=f)
        self.assertEqual(f.getvalue(),
                         '\nUsage: script.py test\n\nTest command\n')

    def test_help(self):
        b = build_baker()
        out = StringIO()
        b.run(["script.py", "--help"], helpfile=out)
        self.assertEqual(out.getvalue(), MAIN_HELP)
        out = StringIO()
        b.run(["script.py", "open", "--help"], helpfile=out)
        self.assertEqual(out.getvalue(), COMMAND_HELP)

    def test_openinput(self):
        b = baker.Baker()
        self.assertTrue(b.openinput('-') is sys.stdin)
        tempdir = tempfile.mkdtemp()
        for ext, opener in [(".gz", gzip.GzipFile), (".bz2", bz2.BZ2File)]:
            g = os.path.join(tempdir, "test" + ext)
            input = self.bytes(INPUT_TEST, 'utf-8')
            fobj = opener(g, "w")
            fobj.write(input)
            fobj.close()
            self.assertEqual(b.openinput(g).read(), input)

    def test_writeconfig(self):
        b = build_baker()
        tempdir = tempfile.mkdtemp()
        ini = os.path.join(tempdir, "conf.ini")
        b.writeconfig(ini)
        with open(ini) as fobj:
            self.assertEqual(fobj.read(), INI_SAMPLE)
        shutil.rmtree(tempdir)

    def test_errors(self):
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
