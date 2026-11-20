#!/bin/sh
set -eu

if [ "$#" -ne 2 ] || [ -z "$1" ]; then
    printf 'Usage: sh capture.sh ADB_SERIAL PACKAGE\n' >&2
    exit 2
fi

adb_bin=${ADB:-adb}
serial=$1
package=$2
case "$package" in
    ''|*[!A-Za-z0-9_.]*) printf 'Use an Android package name\n' >&2; exit 2 ;;
esac
config=$(CDPATH='' cd -- "$(dirname "$0")" && pwd)/frames.pbtxt

device() { "$adb_bin" -s "$serial" "$@"; }

if [ "$(device get-state)" != device ]; then
    printf 'Selected ADB device is unavailable\n' >&2
    exit 1
fi
sdk=$(device shell getprop ro.build.version.sdk | tr -d '\r')
case "$sdk" in
    ''|*[!0-9]*) printf 'Could not determine the Android API level\n' >&2; exit 1 ;;
esac
if [ "$sdk" -lt 31 ]; then
    printf 'FrameTimeline capture requires Android API 31 or higher\n' >&2
    exit 1
fi
if ! device shell pm path "$package" | grep -q '^package:'; then
    printf 'Selected package is unavailable on the device\n' >&2
    exit 1
fi

output=$(mktemp -d "${TMPDIR:-/tmp}/talon-android-perf.XXXXXX")
printf 'Capture directory: %s\n' "$output" >&2
printf 'package=%s\nandroid_api=%s\n' "$package" "$sdk" > "$output/device.txt"
device shell dumpsys -t 10 meminfo "$package" > "$output/meminfo-before.txt"
if ! grep -q '^\*\* MEMINFO in pid' "$output/meminfo-before.txt"; then
    printf 'Launch the package and reach the initial test state before capture\n' >&2
    exit 1
fi
device shell dumpsys -t 10 gfxinfo "$package" reset > "$output/gfxinfo-reset.txt"
printf 'Perform the test action during the 15-second recording\n' >&2
device shell -T perfetto --txt -c - -o - < "$config" > "$output/trace.perfetto-trace"
if [ ! -s "$output/trace.perfetto-trace" ]; then
    printf 'Perfetto returned an empty trace\n' >&2
    exit 1
fi
device shell dumpsys -t 10 gfxinfo "$package" framestats > "$output/framestats.txt"
device shell dumpsys -t 10 meminfo "$package" > "$output/meminfo-after.txt"
if ! grep -q '^\*\* MEMINFO in pid' "$output/meminfo-after.txt"; then
    printf 'Capture ended without a running process for the selected package\n' >&2
    exit 1
fi
printf '%s\n' "$output"
