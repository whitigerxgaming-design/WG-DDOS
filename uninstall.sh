#!/usr/bin/env bash
# WG-DDOS uninstaller - by whitiger
set -uo pipefail
cd "$(dirname "$0")"

echo "This removes the local virtualenv and generated reports."
printf "Continue? [y/N] "
read -r A
case "$A" in
  y|Y) ;;
  *) echo "aborted"; exit 0 ;;
esac

rm -rf .venv
rm -rf reports
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
echo "Done. Source files kept."
echo "WG-DDOS - by whitiger - https://github.com/whitigerxgaming-design"
