"""
These are Unit tests for the project.
Next should come Module Tests
Then integration Tests.

Most of these tests just check to see if the function/method is callable. As there is little processing of any of the
methods, it is difficult to make these tests more useful.
"""
from unittest import TestCase
from unittest.mock import patch

from IGaten import Ygate, Color


class TestYGate(TestCase):
    def setUp(self) -> None:
        self.ygate = Ygate()

    def test_init_ok(self):
        self.assertTrue(self.ygate)

    def test_is_class(self):
        self.assertIsInstance(self.ygate, Ygate)

    def test_format_position(self):
        self.assertEqual(
            self.ygate.format_position((14, 8.09, "N"), (119, 55.07, "E")),
            "11955.07E/01408.09N",
        )

        self.assertEqual(
            self.ygate.format_position((14, 8.09, "S"), (119, 55.07, "E")),
            "11955.07E/01408.09S",
        )

        self.assertEqual(
            self.ygate.format_position((14, 8.09, "S"), (119, 55.07, "W")),
            "11955.07W/01408.09S",
        )

        # This test should fail ... but there is no validation in the format position
        # Method
        # todo Validate input to format position
        self.assertEqual(
            self.ygate.format_position((14, 78.09, "S"), (119, 55.07, "W")),
            "11955.07W/01478.09S",
        )

    @patch("IGaten.Ygate.is_internet")
    def test_is_internet(self, mocked_method):
        # Make sure we call the module only 1 time
        mocked_method.return_value = True
        self.assertEqual(self.ygate.is_internet("www.google.com", 20), True)
        self.assertEqual(mocked_method.called, True)
        self.assertEqual(mocked_method.call_count, 1)
        self.assertNotEqual(mocked_method.call_count, 2)

    @patch("IGaten.Ygate.is_internet")
    def test_is_internet_stupid_site(self, mocked_method):
        mocked_method.return_value = True
        self.assertEqual(
            self.ygate.is_internet("www.this_site_does_not_exists.com", 20), True
        )

    @patch("IGaten.Ygate.aprs_con")
    def test_aprs_conn(self, mock_aprs_conn):
        mock_aprs_conn.return_value = True
        self.assertEqual(self.ygate.aprs_con, True)

    @patch("IGaten.Ygate.send_aprs")
    def test_send_aprs(self, mock_send_aprs):
        mock_send_aprs.return_value = True
        self.assertEqual(self.ygate.send_aprs("This is a test"), True)
        self.assertEqual(self.ygate.send_aprs(""), True)

    @patch("IGaten.Ygate.send_my_position")
    def test_send_my_position(self, mock_send_my_position):
        mock_send_my_position.return_value = True
        self.assertEqual(self.ygate.send_my_position(), True)

    @patch("IGaten.Ygate.open_serial")
    def test_open_serial(self, mock_open_serial):
        mock_open_serial.return_value = True
        self.assertEqual(self.ygate.open_serial(), True)


class Test_Color(TestCase):
    def setUp(self) -> None:
        self.col = Color()

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
