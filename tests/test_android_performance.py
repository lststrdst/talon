import os
from pathlib import Path
import subprocess
import tempfile
import unittest


CAPTURE = (Path(__file__).resolve().parents[1] / "plugins/talon/skills/checks/assets/android-performance/capture.sh")
FAKE_ADB = r'''#!/bin/sh
set -eu
[ "$1 $2" = '-s fixture-device' ] || exit 98
shift 2
printf '%s\n' "$*" >> "$FIXTURE_CALLS"
case "$*" in
    'get-state') printf 'device\n' ;;
    'shell getprop ro.build.version.sdk') printf '%s\n' "$FIXTURE_ANDROID_API" ;;
    'shell pm path org.example.talon') printf 'package:/data/app/fixture/base.apk\n' ;;
    'shell dumpsys -t 10 meminfo org.example.talon')
        printf '** MEMINFO in pid 4 [org.example.talon] **\nTOTAL PSS: 1200\n' ;;
    'shell dumpsys -t 10 gfxinfo org.example.talon reset') ;;
    'shell -T perfetto --txt -c - -o -')
        config=$(cat)
        case "$config" in
            *android.surfaceflinger.frametimeline*) printf '%s' "$FIXTURE_TRACE" ;;
            *) exit 97 ;;
        esac ;;
    'shell dumpsys -t 10 gfxinfo org.example.talon framestats')
        printf '%s\n' '---PROFILEDATA---' 'Flags,IntendedVsync,FrameCompleted' '0,10,20' ;;
    *) exit 96 ;;
esac
'''


class AndroidCaptureTest(unittest.TestCase):
    def run_fixture(self, trace="fixture bytes, not an Android trace", api="34"):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name)
        adb = directory / "adb"
        adb.write_text(FAKE_ADB)
        adb.chmod(0o700)
        calls = directory / "calls.txt"
        result = subprocess.run(["sh", str(CAPTURE), "fixture-device", "org.example.talon"],
                                env=dict(os.environ, ADB=str(adb), TMPDIR=str(directory),
                                         FIXTURE_CALLS=str(calls), FIXTURE_TRACE=trace,
                                         FIXTURE_ANDROID_API=api), capture_output=True, text=True, timeout=10)
        return result, calls.read_text().splitlines()

    def test_captures_before_trace_and_after(self):
        result, calls = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [
            "get-state", "shell getprop ro.build.version.sdk", "shell pm path org.example.talon",
            "shell dumpsys -t 10 meminfo org.example.talon",
            "shell dumpsys -t 10 gfxinfo org.example.talon reset",
            "shell -T perfetto --txt -c - -o -",
            "shell dumpsys -t 10 gfxinfo org.example.talon framestats",
            "shell dumpsys -t 10 meminfo org.example.talon",
        ])
        output = Path(result.stdout.strip())
        self.assertEqual((output / "trace.perfetto-trace").read_text(), "fixture bytes, not an Android trace")
        self.assertIn("0,10,20", (output / "framestats.txt").read_text())
        for name in ("meminfo-before.txt", "meminfo-after.txt"):
            self.assertIn("TOTAL PSS: 1200", (output / name).read_text())

    def test_empty_trace_fails_without_reporting_success_directory(self):
        result, calls = self.run_fixture(trace="")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(calls[-1], "shell -T perfetto --txt -c - -o -")

    def test_old_api_stops_before_collecting_app_data(self):
        result, calls = self.run_fixture(api="30")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Android API 31 or higher", result.stderr)
        self.assertEqual(calls, ["get-state", "shell getprop ro.build.version.sdk"])
