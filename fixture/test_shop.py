import unittest
from discount import apply_discount

class ShopTest(unittest.TestCase):
	def test_discount(self):
		self.assertEqual(apply_discount(20000, 10), 18000)

if __name__ == "__main__":
	unittest.main()
