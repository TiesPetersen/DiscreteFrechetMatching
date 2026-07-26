#!/usr/bin/env bash
# Builds and runs every check in tests/. Exits non-zero if any check fails.

set -euo pipefail
cd "$(dirname "$0")"

# Build the tests
make clean >/dev/null
make all

status=0

# Run the dynamic programming check
echo "=== dynamic_programming_check ==="
./dynamic_programming_check.exe || status=1

echo

# Run the matching check
echo "=== matching_check ==="
./matching_check.exe || status=1

echo

# Run the parent trace check
echo "=== parent_trace_check ==="
./parent_trace_check.exe || status=1

echo

# Run the hand-counted check
echo "=== hand_counted_check ==="
./hand_counted_check.exe || status=1

echo

# Print the final status of the checks
if [ "$status" -eq 0 ]; then
    echo "All checks passed."
else
    echo "One or more checks FAILED."
fi

exit $status
