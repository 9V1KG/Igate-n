"""
These are Unit tests for the project.
Next should come Module Tests
Then integration Tests.

Most of these tests just check to see if the function/method is callable. As there is little processing of any of the
methods, it is difficult to make these tests more useful.
"""
from unittest import TestCase
from unittest.mock import patch, PropertyMock
import IGaten
from IGaten.ygate import Ygate


class TestYGate(TestCase):

    def setUp(self) -> None:
        self.lcl_ygate = Ygate()

    def test_init_ok(self):
        self.assertTrue(self.lcl_ygate)

    def test_is_class(self):
        self.assertIsInstance(self.lcl_ygate, Ygate)


    @patch("IGaten.Ygate.check_routing")
    def test_check_routing(self, mock_check_routing):
        mock_check_routing.return_value = True
        pstr = (
            "DY1P>APWW10,ARISS,RS0ISS,WIDE1-1,WIDE2-1:}DW4TIM>APWW10,TCPIP,DY1P*",
            "}DW4TIM>APWW10,TCPIP,DY1P*:@124210h1309.14N/12345.27E,APRSIS32 de DW4TIM")
        self.assertEqual(
            self.lcl_ygate.check_routing(pstr), True)

    @patch("IGaten.Ygate.is_routing")
    def test_is_routing(self, mock_is_routing):
        mock_is_routing.return_value = True
        self.assertEqual(self.lcl_ygate.is_routing("DK4TB>APW10"), True)
        self.assertEqual(self.lcl_ygate.is_routing("E2X"), True)
        mock_is_routing.return_value = False
        self.assertEqual(self.lcl_ygate.is_routing(" E2X"), False)
        self.assertEqual(self.lcl_ygate.is_routing("^%4DK4TB=9U"), False)

    def test_aprs_conn(self):
        with patch(
            "IGaten.Ygate.aprs_con", new_callable=PropertyMock
        ) as mock_aprs_conn:
            mock_aprs_conn.return_value = True
            self.assertEqual(self.lcl_ygate.aprs_con, True)

    @patch("IGaten.Ygate.send_aprs")
    def test_send_aprs(self, mock_send_aprs):
        mock_send_aprs.return_value = True
        self.assertEqual(self.lcl_ygate.send_aprs("This is a test"), True)
        self.assertEqual(self.lcl_ygate.send_aprs(""), True)

    @patch("IGaten.Ygate.send_my_position")
    def test_send_my_position(self, mock_send_my_position):
        mock_send_my_position.return_value = True
        self.assertEqual(self.lcl_ygate.send_my_position(), True)

    @patch("IGaten.Ygate.open_serial")
    def test_open_serial(self, mock_open_serial):
        mock_open_serial.return_value = True
        self.assertEqual(self.lcl_ygate.open_serial(), True)

    @patch("IGaten.Ygate.get_data_type")
    def test_get_data_type(self, mock_get_data_type):
        pld = ":DY1P APRS 10 Watts RF-IS-RF Digipeater"
        mock_get_data_type.return_value = "MSG "
        self.assertEqual(self.lcl_ygate.get_data_type(pld), "MSG ")
        pld = ":DU1KG-10 APRS 10 Watts RF-IS-RF Digipeater"
        mock_get_data_type.return_value = '\033[1;35;48mMSG \033[1;37;0m'
        self.assertEqual(self.lcl_ygate.get_data_type(pld), '\033[1;35;48mMSG \033[1;37;0m')
