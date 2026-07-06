import unittest


class BenchmarkImportTests(unittest.TestCase):
    def test_physics_package_imports(self):
        from benchmark import physics

        self.assertEqual(physics.__name__, "benchmark.physics")


if __name__ == "__main__":
    unittest.main()
