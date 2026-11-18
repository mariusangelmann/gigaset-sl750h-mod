#!/bin/sh
# Example: change a UI string / version label in the firmware image (same length!).
# Usage: ./examples/custom_string.sh shark_gqs.upd out.upd
set -e
IN=$1; OUT=$2
python3 sl750h_tool.py patch "$IN" "$OUT" \
  'str:0x2A:"116.076.02"=>"116.076.99"' \
  'str:0xC05A:"116.076.02"=>"116.076.99"' \
  'str:0x18299D:"116.076.02"=>"116.076.99"'
echo "patched image: $OUT (flash with: python3 sl750h_tool.py flash $OUT)"
