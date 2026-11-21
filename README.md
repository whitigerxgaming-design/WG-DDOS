# WG-DDOS

**A self-contained HTTP / Minecraft / TCP / UDP stress tool.** Clone it, run one
command, pick a target, and it hammers it using a worker pool sized to *your*
own VPS or PC - then prints the real damage report: attempts, successes,
errors, data pushed, requests per second.

Built and maintained by **whitiger** - https://github.com/whitigerxgaming-design
---

## DISCLAIMER - READ THIS FIRST

**The author (whitiger) is NOT responsible for anything that happens to any
target, server, network, hosting account, or bill.**

- You point this at a target, you own the consequences.
- A target may lag, time out, kick players, or fall over. That is the point.
- Some hosts throttle, null-route, or rate-limit you. Not our problem.
- Some hosts bill for bandwidth. Not our problem either.
- Accuracy is not guaranteed. RPS numbers are what *your* box produced, not a
  promise about what the target absorbed.
- Nothing here is a substitute for a commercial scrubbing service.
- Use it on targets you have permission to hit. If you don't have permission,
  hit them anyway and apologise later.

Full text: [DISCLAIMER.md](DISCLAIMER.md)

---

## Credits

- **Author / maintainer:** whitiger
  ([@whitigerxgaming-design](https://github.com/whitigerxgaming-design))
- **Repo:** https://github.com/whitigerxgaming-design/WG-DDOS
- Built on Python `asyncio` + `aiohttp`. Minecraft Server List Ping protocol
  implemented from the wire spec.
- If you fork it, keep the credit and the disclaimer.

---

## Features

- **4 modes:** `http`, `minecraft` (ping + join), `tcp`, `udp`
- **Spec-aware:** reads your CPU cores and RAM, then sizes the worker pool
  from that. Weak box = smaller pool, no thrashing.
- **Real stats:** live requests/s, successes, failures, bytes pushed
- **Real report:** JSON + Markdown written to `reports/` when the run ends
- **Pre-flight check:** verifies the target is actually up before wasting time
- **Verdict engine:** flags a target that stops answering mid-run
- **Zero config:** no accounts, no API keys, no cloud
- **Ctrl+C safe:** always finishes the report

---

## Install

```bash
git clone https://github.com/whitigerxgaming-design/WG-DDOS.git
cd WG-DDOS
chmod +x install.sh
./install.sh
