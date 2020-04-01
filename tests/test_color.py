"""
These are Unit tests for the project.
Next should come Module Tests
Then integration Tests.

Most of these tests just check to see if the function/method is callable. As there is little processing of any of the
methods, it is difficult to make these tests more useful.
"""
from unittest import TestCase


import IGaten


class Test_Color(TestCase):
    def setUp(self) -> None:
        self.col = IGaten.Color()

    def test_color_not_changed(self):
        """
        In case the Colors have some significance you can try something like this.
        """
        self.assertEqual(self.col.PURPLE, "\033[1;35;48m")
        self.assertEqual(self.col.CYAN, "\033[1;36;48m")
        self.assertEqual(self.col.BOLD, "\033[1;37;48m")
        self.assertEqual(self.col.BLUE, "\033[1;34;48m")
        self.assertEqual(self.col.GREEN, "\033[1;32;48m")
        self.assertEqual(self.col.YELLOW, "\033[1;33;48m")
        self.assertEqual(self.col.RED, "\033[1;31;48m")
        self.assertEqual(self.col.BLACK, "\033[1;30;48m")
        self.assertEqual(self.col.UNDERLINE, "\033[4;37;48m")
        self.assertEqual(self.col.END, "\033[1;37;0m")
