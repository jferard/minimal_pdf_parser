import unittest

from pdf_operation import ModifyCTM, AppendRectangle


class OperationTestCase(unittest.TestCase):
    def test_rpr(self):
        print(ModifyCTM(1, 2, 3, 4, 5, 6))
        print(AppendRectangle(1, 2, 3, 4))


if __name__ == '__main__':
    unittest.main()
