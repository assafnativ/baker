import unittest

import baker


class TestBaker(unittest.TestCase):
    def test_simple(self):
        b = baker.Baker()
        @b.command
        def test(a, b, c):
            return (a, b, c)
        self.assertEqual(b.run(["s", "test", "1", "2", "3"], main=False), ("1", "2", "3"))

    def test_default(self):
        b = baker.Baker()
        @b.command(default=True)
        def test(a="a", b="b", c="c"):
            return (a, b, c)
        self.assertEqual(b.run(["s", "1", "2", "3"], main=False), ("1", "2", "3"))
        self.assertEqual(b.run(["s"], main=False), ("a", "b", "c"))

    def test_options(self):
        b = baker.Baker()
        @b.command
        def test(a="a", b="b", c="c"):
            return (a, b, c)
        self.assertEqual(b.run(["s", "test", "--a", "alfa", "--b=bravo"], main=False),
                         ("alfa", "bravo", "c"))
    
    def test_shortopts(self):
        b = baker.Baker()
        @b.command(shortopts={"alfa":"a", "bravo":"b", "charlie":"c"})
        def test(alfa="1", bravo="2", charlie=False):
            return (alfa, bravo, charlie)
        self.assertEqual(b.run(["s", "test", "-a", "100", "-cb200"], main=False),
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
        
        self.assertEqual(b.run(["s", "test", "--a", "1", "--b", "2"], main=False),
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

    def test_usage(self):
        b = baker.Baker()
        @b.command
        def test():
            "Test command"
            pass
        
        from cStringIO import StringIO
        f = StringIO()
        b.usage("test", scriptname="script.py", file=f)
        self.assertEqual(f.getvalue(), '\nUsage: script.py test\n\nTest command\n')
        
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
