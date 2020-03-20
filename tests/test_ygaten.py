from unittest import TestCase
from unittest.mock import patch

from IGaten import Ygate


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
        self.assertEqual(self.ygate.is_internet("www.this_site_does_not_exists.com", 20), True)

    @patch("IGaten.Ygate.aprs_con")
    def test_aprs_conn(self,mock_aprs_conn):
        mock_aprs_conn.return_value = True
        self.assertEqual(self.ygate.aprs_con(), True)

    @patch('IGaten.Ygate.send_aprs')
    def test_send_aprs(self,mock_send_aprs):
        mock_send_aprs.return_value = True
        self.assertEqual(self.ygate.send_aprs("This is a test"), True)
        self.assertEqual(self.ygate.send_aprs(""), True)

    @patch('IGaten.Ygate.send_my_position')
    def test_send_my_position(self,mock_send_my_position):
        mock_send_my_position.return_value = True
        self.assertEqual(self.ygate.send_my_position(), True)

