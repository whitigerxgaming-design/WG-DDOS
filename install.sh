#!/usr/bin/env bash
# WG-DDOS installer - by whitiger
# https://github.com/whitigerxgaming-design/WG-DDOS
# AS IS, no warranty. Author is not responsible for anything. See DISCLAIMER.md.
set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YEL='\033[0;33m'; NC='\033[0m'
say() { printf "${GREEN}[+] %s${NC}\n" "$*"; }
warn() { printf "${YEL}[!] %s${NC}\n" "$*"; }
die() { printf "${RED}[x] %s${NC}\n" "$*" >&2; exit 1; }

cd "$(dirname "$0")"

echo "=============================================="
echo " WG-DDOS installer  -  by whitiger"
echo " https://github.com/whitigerxgaming-design"
echo " AS IS, no warranty. Author not responsible."
echo "=============================================="

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || die "Python 3.9+ not found. Install python3 first."

$PY - <<'EOF' || die "Python 3.9+ required."
import sys
sys.exit(0 if sys.version_info >= (3, 9) else 1)
EOF
say "Python: $($PY -V 2>&1)"

if ! $PY -c "import venv" >/dev/null 2>&1; then
  warn "venv module missing, trying to install it"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y python3-venv
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --noconfirm python
  else
    die "Install the python3-venv package manually."
  fi
fi

if [ ! -d .venv ]; then
  say "Creating virtualenv (.venv)"
  $PY -m venv .venv
else
  say "Virtualenv already present"
fi
. .venv/bin/activate

say "Upgrading pip"
python -m pip install --quiet --upgrade pip

say "Installing dependencies"
python -m pip install --quiet -r requirements.txt

say "Setting permissions"
chmod +x wgddos.py wgddos.sh uninstall.sh 2>/dev/null || true

UL=$(ulimit -n 2>/dev/null || echo 1024)
if [ "$UL" -lt 8192 ] 2>/dev/null; then
  warn "Open-file limit is $UL. For real load run: ulimit -n 65535"
fi

echo
echo "=============================================="
echo " Done."
echo
echo " Activate the env first:     source .venv/bin/activate"
echo " Then run:                   ./wgddos.sh"
echo " Or directly:                ./wgddos.py http https://example.com"
echo " Check what your box can do: ./wgddos.py specs"
echo "=============================================="
echo " Remember: author is NOT responsible for any target."
