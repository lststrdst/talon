"""Run a project check and report its exit status, marker match and JUnit counts."""

import argparse
import json
import os
import stat
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree


MAX_JUNIT_BYTES = 10 * 1024 * 1024
SUITE_TAGS = ("testsuites", "testsuite")
FAILURE_COUNTS = {"failure": "failures", "error": "errors"}


class JUnitReportError(Exception):
    """A fixed error code suitable for the JSON summary."""


class JUnitTreeBuilder(ElementTree.TreeBuilder):
    def doctype(self, name, public_id, system_id):
        raise JUnitReportError("JUnitReportInvalid")

    def data(self, data):
        # Text in test reports can contain logs and secrets that the counter never uses.
        pass


def contains_output(stream, expected):
    if not expected:
        return None
    expected = expected.encode("utf-8")
    stream.seek(0)
    tail = b""
    for chunk in iter(lambda: stream.read(65536), b""):
        block = tail + chunk
        if expected in block:
            return True
        tail = block[-(len(expected) - 1):] if len(expected) > 1 else b""
    return False


def require_new_report(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise JUnitReportError("JUnitReportUnreadable") from error
    raise JUnitReportError("JUnitReportExists")


def read_junit(path):
    flags = getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise JUnitReportError("JUnitReportNotFile")
        with open(path, "rb", opener=lambda name, mode: os.open(name, mode | flags)) as report:
            if not stat.S_ISREG(os.fstat(report.fileno()).st_mode):
                raise JUnitReportError("JUnitReportNotFile")
            contents = report.read(MAX_JUNIT_BYTES + 1)
    except FileNotFoundError as error:
        raise JUnitReportError("JUnitReportMissing") from error
    except OSError as error:
        raise JUnitReportError("JUnitReportUnreadable") from error
    if len(contents) > MAX_JUNIT_BYTES:
        raise JUnitReportError("JUnitReportTooLarge")

    try:
        root = ElementTree.fromstring(contents, parser=ElementTree.XMLParser(target=JUnitTreeBuilder()))
    except (ElementTree.ParseError, LookupError, ValueError) as error:
        raise JUnitReportError("JUnitReportInvalid") from error
    return count_junit(root)


def local_tag(element):
    return element.tag.rsplit("}", 1)[-1]


def count_junit(root):
    if local_tag(root) not in SUITE_TAGS:
        raise JUnitReportError("JUnitReportInvalid")

    suites = [root]
    for suite in suites:
        suites.extend(child for child in suite if local_tag(child) in SUITE_TAGS)

    suite_counts = {}
    for suite in reversed(suites):
        counts = Counter()
        for child in suite:
            tag = local_tag(child)
            if tag in SUITE_TAGS:
                counts.update(suite_counts.pop(child))
            elif tag in FAILURE_COUNTS:
                counts[FAILURE_COUNTS[tag]] += 1
            elif tag == "testcase":
                outcomes = {local_tag(outcome) for outcome in child}
                counts["tests"] += 1
                if "skipped" in outcomes or child.get("status", "").lower() in ("notrun", "skipped"):
                    counts["skipped"] += 1
                for outcome, field in FAILURE_COUNTS.items():
                    counts[field] += outcome in outcomes

        # Suite totals can include runner errors that have no testcase element.
        for field in ("skipped", "failures", "errors"):
            declared = suite.get(field, "0")
            if len(declared) > 10 or not declared.isascii() or not declared.isdecimal():
                raise JUnitReportError("JUnitReportInvalid")
            counts[field] = max(counts[field], int(declared))
        if counts["skipped"] > counts["tests"]:
            raise JUnitReportError("JUnitReportInvalid")
        suite_counts[suite] = counts

    counts = suite_counts[root]
    return {
        "tests": counts["tests"],
        "executed": counts["tests"] - counts["skipped"],
        "skipped": counts["skipped"],
        "failures": counts["failures"],
        "errors": counts["errors"],
    }


def require_passed_tests(counts):
    if counts["failures"] or counts["errors"]:
        raise JUnitReportError("JUnitTestFailures")
    if not counts["tests"]:
        raise JUnitReportError("JUnitNoTests")
    if not counts["executed"]:
        raise JUnitReportError("JUnitAllSkipped")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Short check name for the report")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds")
    parser.add_argument("--expect", help="Literal UTF-8 marker expected on stdout")
    parser.add_argument("--junit", type=Path, help="New JUnit XML file written by the command")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else []
    if not command or args.timeout <= 0 or args.expect == "":
        parser.error("provide -- COMMAND with a positive timeout and a non-empty marker if supplied")

    result = {"check": args.label, "status": "NOT_RUN", "exit_code": None, "stdout_match": None}
    if args.junit is not None:
        result["junit"] = None
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdout:
        try:
            if args.junit is not None:
                require_new_report(args.junit)
            completed = subprocess.run(
                command, stdin=subprocess.DEVNULL, stdout=stdout,
                stderr=subprocess.DEVNULL, timeout=args.timeout, check=False,
            )
            result["exit_code"] = completed.returncode
            result["stdout_match"] = contains_output(stdout, args.expect)
            result["status"] = "PASS" if completed.returncode == 0 and result["stdout_match"] is not False else "FAIL"
            if args.junit is not None:
                result["junit"] = read_junit(args.junit)
                require_passed_tests(result["junit"])
        except subprocess.TimeoutExpired:
            result["status"] = "TIMEOUT"
        except JUnitReportError as error:
            result["error"] = str(error)
            if result["exit_code"] is not None:
                result["status"] = "FAIL"
        except OSError as error:
            result["error"] = type(error).__name__

    result["duration_seconds"] = round(time.monotonic() - started, 3)
    print(json.dumps(result))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
