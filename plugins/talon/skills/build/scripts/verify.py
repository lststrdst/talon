"""Run a project check and emit its exit status and optional output assertion."""

import argparse
import json
import subprocess
import tempfile
import time


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Short check name for the report")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds")
    parser.add_argument("--expect", help="Literal UTF-8 marker expected on stdout")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else []
    if not command or args.timeout <= 0 or args.expect == "":
        parser.error("provide -- COMMAND with a positive timeout and a non-empty marker if supplied")

    result = {"check": args.label, "status": "NOT_RUN", "exit_code": None, "stdout_match": None}
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdout:
        try:
            completed = subprocess.run(
                command, stdin=subprocess.DEVNULL, stdout=stdout,
                stderr=subprocess.DEVNULL, timeout=args.timeout, check=False,
            )
            result["exit_code"] = completed.returncode
            result["stdout_match"] = contains_output(stdout, args.expect)
            result["status"] = "PASS" if completed.returncode == 0 and result["stdout_match"] is not False else "FAIL"
        except subprocess.TimeoutExpired:
            result["status"] = "TIMEOUT"
        except OSError as error:
            result["error"] = type(error).__name__

    result["duration_seconds"] = round(time.monotonic() - started, 3)
    print(json.dumps(result))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
