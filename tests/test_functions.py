"""
These are Unit tests for the project.
Next should come Module Tests
Then integration Tests.

Most of these tests just check to see if the function/method is callable. As there is little processing of any of the
methods, it is difficult to make these tests more useful.
"""
from unittest import TestCase
from unittest.mock import patch
import IGaten


class TestFunctions(TestCase):
    def setUp(self) -> None:
        junk = 1

    def test_decode_ascii(self):
        print("Test decode_ascii:")
        b_str = b'test byte string with 2\xb0 invalid\xef chars'
        r_str = IGaten.decode_ascii(b_str)
        self.assertEqual(r_str[0], 2)
        print(r_str[1])
        b_str = b'test byte string with all valid ASCII chars'
        r_str = IGaten.decode_ascii(b_str)
        print(r_str[1])
        self.assertEqual(r_str[0], 0)

    def test_b91_encode(self):
        # 0 bits set
        self.assertEqual(IGaten.b91_encode(0), "")
        # 1 LSB Set
        self.assertEqual(IGaten.b91_encode(90), "{")
        self.assertEqual(IGaten.b91_encode(91), '"!')
        # 2 LSB Set
        self.assertEqual(IGaten.b91_encode(91 + 90), '"{')
        self.assertEqual(IGaten.b91_encode(91 ** 2), '"!!')
        self.assertEqual(IGaten.b91_encode(91 ** 3), '"!!!')
        # All Bits Set
        self.assertEqual(IGaten.b91_encode((91 ** 4) - 1), "{{{{")
        # There are 91**4 -1 possible combinations however.... !!

    def test_b91_decode(self):
        self.assertEqual(IGaten.b91_decode(''), 0)
        self.assertEqual(IGaten.b91_decode('{'), 90)
        self.assertEqual(IGaten.b91_decode('"!'), 91)
        self.assertEqual(IGaten.b91_decode('"{'), 91 + 90)
        self.assertEqual(IGaten.b91_decode('"!!'), 91 ** 2)
        self.assertEqual(IGaten.b91_decode('"!!!'), 91 ** 3)
        self.assertEqual(IGaten.b91_decode('{{{{'), (91 ** 4) - 1)


    @patch("IGaten.is_internet")
    def test_is_internet(self, mocked_method):
        # Make sure we call the module only 1 time
        mocked_method.return_value = True
        self.assertEqual(IGaten.is_internet(), True)
        self.assertEqual(mocked_method.called, True)
        self.assertEqual(mocked_method.call_count, 1)
        self.assertEqual(IGaten.is_internet("yaesu.com"), True)
        self.assertEqual(mocked_method.call_count, 2)

    @patch("IGaten.is_internet")
    def test_is_internet_stupid_site(self, mocked_method):
        mocked_method.return_value = True
        self.assertEqual(
            IGaten.is_internet("www.this_site_does_not_exists.com", 20), True
        )

    def test_compress_position(self):
        """
        Check the position compression
        :return:
        """
        lon1 = (10.11, 20.22, "E")
        lat2 = (54.11, 2.22, "N")
        res = IGaten.compress_position(lon1, lat2)
        self.assertEqual(res, "/3,6\\Q-:T#   ")
        res = IGaten.compress_position(lon1, lat2, alt=(150, "m"))
        self.assertEqual(res, "/3,6\\Q-:T#C)t")

        # As location is calculated to a meter ... adding more accuract in the DD.MMMMM input should change the output
        lon1 = (10.111111, 20.222222, "E")
        lat2 = (54.111111, 2.2222222, "N")
        res = IGaten.compress_position(lon1, lat2)
        self.assertEqual(res, "/3,1nQ-<y#   ")
        res = IGaten.compress_position(lon1, lat2, alt=(150, "m"))
        self.assertEqual(res, "/3,1nQ-<y#C)t")

    def test_lm(self):
        self.assertEqual(IGaten.cnv_ch("0"), "0")
        self.assertEqual(IGaten.cnv_ch("A"), "0")
        self.assertEqual(IGaten.cnv_ch("P"), "0")
        self.assertEqual(IGaten.cnv_ch("K"), "0")
        self.assertEqual(IGaten.cnv_ch("L"), "0")
        self.assertEqual(IGaten.cnv_ch("Z"), "0")

    def test_mic_e_decode(self):
        self.assertEqual(IGaten.mic_e_decode(
            " ",
            b'`0V l\x1c -/`":-}435.350MHz DU1KG home 73 Klaus_%'),
            "Invalid destination field")
        self.assertEqual(IGaten.mic_e_decode(
            "DU1KG-1>Q4PWQ0,DY1P,WIDE1*,WIDE2-1,qAR,DU1KG-10:",
            b'`0V l \x1c-/`":-}435.350MHz DU1KG home 73 Klaus_%'),
            "Pos: 14 7.1'N, 120 58.04'E, In Service, Alt: 568 m, ")
        self.assertEqual(IGaten.mic_e_decode(
            "DU1KG-1>Q4PWQ0,DY1P,WIDE1*,WIDE2-1,qAR,DU1KG-10:", b''),
            "Invalid information field")
