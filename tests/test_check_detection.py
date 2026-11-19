"""Exercise the public stack detector used to select bug-finding tests."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


DETECTOR = Path(__file__).resolve().parents[1] / "plugins/talon/skills/stack/scripts/detect.py"


class CheckDetectionTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name)

    def detect(self, target):
        output = subprocess.check_output(
            [sys.executable, str(DETECTOR), "--project", str(self.project), "--target", target],
            text=True,
        )
        return json.loads(output)

    def test_declared_testing_tools_are_scoped_to_the_component(self):
        api = self.project / "api"
        ui = self.project / "ui"
        api.mkdir()
        ui.mkdir()
        (api / "requirements-dev.txt").write_text("pytest\nhypothesis>=6\n")
        (api / "pyproject.toml").write_text('[tool.mutmut]\nsource_paths = ["src/"]\n')
        (ui / "package.json").write_text(json.dumps({
            "devDependencies": {"fast-check": "4", "@stryker-mutator/core": "9"},
        }))

        server = self.detect("api")
        self.assertEqual(server["signals"]["hypothesis"], ["api/requirements-dev.txt"])
        self.assertEqual(server["runners"]["mutmut"], ["api/pyproject.toml"])
        self.assertNotIn("stryker", server["runners"])
        browser = self.detect("ui")
        self.assertEqual(browser["signals"]["fast-check"], ["ui/package.json"])
        self.assertEqual(browser["runners"]["stryker"], ["ui/package.json"])
        self.assertNotIn("hypothesis", browser["signals"])

    def test_names_in_product_metadata_do_not_enable_testing_tools(self):
        (self.project / "package.json").write_text(json.dumps({
            "name": "fast-check", "description": "@stryker-mutator/core",
        }))
        (self.project / "pyproject.toml").write_text(
            '[project]\nname = "hypothesis"\ndescription = "mutmut"\n'
        )
        result = self.detect(".")
        self.assertNotIn("hypothesis", result["signals"])
        self.assertNotIn("fast-check", result["signals"])
        self.assertNotIn("mutmut", result["runners"])
        self.assertNotIn("stryker", result["runners"])


if __name__ == "__main__":
    unittest.main()
