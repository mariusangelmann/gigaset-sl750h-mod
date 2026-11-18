#!/bin/sh
# Example: convert a WAV to a G.722 ringtone and upload it to the handset
# (handset must be on its base: AT+CSQ > 0, AT^SGST = 1,1).
# Usage: ./examples/ringtone.sh song.wav MyRingtone
set -e
python3 sl750h_tool.py ringtone "$1" "$2"
