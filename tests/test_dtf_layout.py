"""Layout check for the dtf package.

Imports each dtf subpackage. Lives flat in tests/ (no tests/dtf/ folder) so the
test directory cannot shadow the top-level dtf package.

Run from the repository root:
    python -m unittest discover -s tests -p "test_dtf_layout.py" -v
"""

import importlib
import unittest

SUBPACKAGES = ("bank", "render", "probes", "repairs", "diagnoser", "eval")


class DtfLayoutTest(unittest.TestCase):
    def test_subpackages_import(self) -> None:
        for name in SUBPACKAGES:
            with self.subTest(subpackage=name):
                module = importlib.import_module(f"dtf.{name}")
                self.assertEqual(module.__name__, f"dtf.{name}")


if __name__ == "__main__":
    unittest.main()
