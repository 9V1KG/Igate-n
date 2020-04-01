"""
These are Unit tests for the project.
Next should come Module Tests
Then integration Tests.

Most of these tests just check to see if the function/method is callable. As there is little processing of any of the
methods, it is difficult to make these tests more useful.
"""
from unittest import TestCase
from unittest.mock import patch
from IGaten.ygate import Ygate
import IGaten


class TestFunctions(TestCase):
    def setUp(self) -> None:
        junk=1

    def test_b91(self):
        # 0 bits set
        self.assertEqual(IGaten.functions.b91(0), '!!!!')
        # 1 LSB Set
        self.assertEqual(IGaten.functions.b91(90), '!!!{')
        self.assertEqual(IGaten.functions.b91(91), '!!"!')
        # 2 LSB Set
        self.assertEqual(IGaten.functions.b91(91 + 90), '!!"{')
        self.assertEqual(IGaten.functions.b91(91 ** 2), '!"!!')
        self.assertEqual(IGaten.functions.b91(91 ** 3), '"!!!')
        # All Bits Set
        self.assertEqual(IGaten.functions.b91((91 ** 4) -1), '{{{{')
        # There are 91**4 -1 possible combinations however.... !!

    @patch("IGaten.functions.is_internet")
    def test_is_internet(self, mocked_method):
        # Make sure we call the module only 1 time
        mocked_method.return_value = True
        self.assertEqual(IGaten.functions.is_internet(), True)
        self.assertEqual(mocked_method.called, True)
        self.assertEqual(mocked_method.call_count, 1)

    @patch("IGaten.functions.is_internet")
    def test_is_internet_stupid_site(self, mocked_method):
        mocked_method.return_value = True
        self.assertEqual(
            IGaten.functions.is_internet("www.this_site_does_not_exists.com", 20), True
        )


    def test_compress_position(self):
        """
        Check the position compression
        :return:
        """
        lon1 = (10.11,20.22, 'E')
        lat2 = (54.11, 2.22, 'N')
        res = IGaten.functions.compress_position(lon1,lat2)
        self.assertEqual(res,'/3,6\\Q-:T#   ')
        res = IGaten.functions.compress_position(lon1, lat2, alt=(150,'m'))
        self.assertEqual(res, '/3,6\\Q-:T#C)t')

        # As location is calculated to a meter ... adding more accuract in the DD.MMMMM input should change the output
        lon1 = (10.111111, 20.222222, 'E')
        lat2 = (54.111111, 2.2222222, 'N')
        res = IGaten.functions.compress_position(lon1, lat2)
        self.assertEqual(res, '/3,1nQ-<y#   ')
        res = IGaten.functions.compress_position(lon1, lat2, alt=(150, 'm'))
        self.assertEqual(res, '/3,1nQ-<y#C)t')



