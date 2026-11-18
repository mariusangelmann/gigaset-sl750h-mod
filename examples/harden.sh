#!/bin/sh
# Example: build the security-hardened image (neuter all plaintext HTTP update/
# telemetry endpoints + version bump + CRC fixer). Flash over USB afterwards.
# Usage: ./examples/harden.sh shark_gqs.upd hardened.upd [version]
set -e
IN=$1; OUT=$2; VER=${3:-116.076.06}
python3 make_hardened.py "$IN" "$OUT" "$VER"
echo "hardened image: $OUT (flash with: python3 sl750h_tool.py flash $OUT)"
