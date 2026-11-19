"""Check Talon's JUnit accounting across nested, mixed-status reports."""

import importlib.util
import itertools
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


SCRIPT = Path(__file__).resolve().parents[1] / "plugins/talon/skills/build/scripts/verify.py"
SPEC = importlib.util.spec_from_file_location("talon_verify", SCRIPT)
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


class JUnitOutcomesTest(unittest.TestCase):
    def test_nested_reports_count_each_case_once(self):
        outcomes = ("passed", "skipped", "failure", "error")
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "results.xml"
            for cases in itertools.product(outcomes, repeat=3):
                with self.subTest(cases=cases):
                    root = ET.Element("testsuites", tests="3", skipped=str(cases.count("skipped")))
                    first = ET.SubElement(root, "testsuite")
                    second = ET.SubElement(root, "testsuite")
                    groups = (first, ET.SubElement(first, "testsuite"), second)
                    for parent, outcome in zip(groups, cases):
                        case = ET.SubElement(parent, "testcase")
                        if outcome != "passed":
                            ET.SubElement(case, outcome)
                    ET.ElementTree(root).write(report, encoding="utf-8")

                    counts = verify.read_junit(report)
                    self.assertEqual(counts, {
                        "tests": 3,
                        "executed": 3 - cases.count("skipped"),
                        "skipped": cases.count("skipped"),
                        "failures": cases.count("failure"),
                        "errors": cases.count("error"),
                    })
                    if "failure" in cases or "error" in cases:
                        with self.assertRaisesRegex(verify.JUnitReportError, "JUnitTestFailures"):
                            verify.require_passed_tests(counts)
                    elif cases.count("skipped") == len(cases):
                        with self.assertRaisesRegex(verify.JUnitReportError, "JUnitAllSkipped"):
                            verify.require_passed_tests(counts)
                    else:
                        verify.require_passed_tests(counts)
