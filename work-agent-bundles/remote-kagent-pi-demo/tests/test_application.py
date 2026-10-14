"""Real checkout behavior and the deliberately failing image version."""
import unittest
import application


class Checkout(unittest.TestCase):
    def tearDown(self):
        application.VERSION = 'v1'

    def test_guest_and_loyalty_on_healthy_version(self):
        application.VERSION = 'v1'
        self.assertEqual(application.checkout({'name': 'Guest'})['total'], 20)
        self.assertEqual(application.checkout({'loyalty': {'discount': 3}})['total'], 17)

    def test_regression_is_specific_to_guest(self):
        application.VERSION = 'v2'
        with self.assertRaises(KeyError): application.checkout({'name': 'Guest'})
        self.assertEqual(application.checkout({'loyalty': {'discount': 3}})['total'], 17)
