#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WG-DDOS interactive panel.

Shows a numbered menu, collects the target, then hands off to wgddos.py.

by whitiger - https://github.com/whitigerxgaming-design/WG-DDOS
AS IS, no warranty. The author is NOT responsible for any target. See DISCLAIMER.md.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    import wgddos
except ImportError:
    sys.exit("wgddos.py is missing - clone the full repo again")


def ask(prompt: str, default: str = "") -> str:
    try:
        val = input(prompt).strip()
    except EOFError:
        return default
    return val or default


def ask_num(prompt: str, default: str) -> str:
    while True:
        raw = ask(prompt, default)
        try:
            n = float(raw)
            if n > 0:
                return str(int(n) if n == int(n) else n)
        except ValueError:
            pass
        print(f"    '{raw}' is not a positive number, try again")


def render() -> None:
    sp = wgddos.specs()
    print(wgddos.BANNER.format(ver=wgddos.VERSION, repo=wgddos.REPO))
    print(f"  This box: {sp['cores']} core(s), {sp['ram_gb']} GB RAM, {sp['platform']}")
    print()
    print("  What do you want to hit?")
    print()
    print("    1) Website  (HTTP / HTTPS)")
    print("    2) Minecraft server")
    print("    3) TCP port")
    print("    4) UDP port")
    print("    5) Just show what this machine can do")
    print("    6) Quit")
    print()


def build_argv(choice: str):
    if choice == "1":
        target = ask("  Website URL or host (e.g. https://example.com): ")
        if not target:
            print("    cancelled")
            return None
        dur = ask_num("  Duration in seconds [30]: ", "30")
        argv = ["http", target, "--duration", dur]

    elif choice == "2":
        target = ask("  Minecraft server host or IP: ")
        if not target:
            print("    cancelled")
            return None
        port = ask("  Port [25565]: ", "25565")
        kind = ask("  Flood type - 1) ping  2) join  [1]: ", "1")
        dur = ask_num("  Duration in seconds [30]: ", "30")
        argv = ["minecraft", target, "--port", port, "--duration", dur,
                "--mc-mode", "join" if kind == "2" else "ping"]

    elif choice == "3":
        target = ask("  Host or IP: ")
        if not target:
            print("    cancelled")
            return None
        port = ask("  Port [80]: ", "80")
        dur = ask_num("  Duration in seconds [30]: ", "30")
        argv = ["tcp", target, "--port", port, "--duration", dur]

    elif choice == "4":
        target = ask("  Host or IP: ")
        if not target:
            print("    cancelled")
            return None
        port = ask("  Port [53]: ", "53")
        dur = ask_num("  Duration in seconds [30]: ", "30")
        argv = ["udp", target, "--port", port, "--duration", dur]

    else:
        return None

    workers = ask("  Workers [auto]: ", "")
    if workers:
        argv += ["--workers", workers]

    print()
    print("  " + "-" * 46)
    print(f"  Target   : {target}")
    print(f"  Mode     : {argv[0]}")
    if "--port" in argv:
        print(f"  Port     : {argv[argv.index('--port') + 1]}")
    print(f"  Duration : {argv[argv.index('--duration') + 1]}s")
    print(f"  Workers  : {workers or 'auto (sized to this box)'}")
    print("  " + "-" * 46)
    if ask("  Start? [Y/n]: ", "y").lower().startswith("n"):
        print("    cancelled")
        return None
    return argv


def main() -> int:
    while True:
        render()
        choice = ask("  Type a number [1-6]: ")

        if choice == "5":
            wgddos.cmd_specs()
            ask("\n  Press Enter for the menu...")
            print("\n" * 2)
            continue

        if choice in ("6", "q", "quit", "exit"):
            print("\n  Done. Author is not responsible for any target.")
            return 0

        if choice not in ("1", "2", "3", "4"):
            print("    pick 1-6")
            continue

        argv = build_argv(choice)
        if not argv:
            print("\n" * 2)
            continue

        print()
        try:
            wgddos.main(argv)
        except KeyboardInterrupt:
            print("\n  [interrupted]")

        ask("\n  Press Enter for the menu...")
        print("\n" * 2)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  bye")
        sys.exit(130)
