#!/usr/bin/env python
"""
Ahoum Events Platform — Cross-platform verification script.
Works on Linux, macOS, and Windows.

Usage:
    python verify.py
"""
import os
import re
import subprocess
import sys
import tempfile

# ── Colors (disabled on Windows unless supported) ───────────
if sys.platform == "win32":
    try:
        os.system("")  # Enable ANSI on Windows 10+
    except Exception:
        pass

GREEN = "\033[0;32m"
RED = "\033[0;31m"
BOLD = "\033[1m"
RESET = "\033[0m"
CHECK = f"{GREEN}✓{RESET}"
CROSS = f"{RED}✗{RESET}"


def header():
    print()
    print("╔════════════════════════════════════════════╗")
    print("║       Ahoum Events Platform                ║")
    print("║       Backend Verification                 ║")
    print("╚════════════════════════════════════════════╝")
    print()


def fail_footer():
    print()
    print("╔════════════════════════════════════════════╗")
    print(f"║         {RED}VERIFICATION FAILED{RESET}               ║")
    print("╚════════════════════════════════════════════╝")
    print()


def pass_footer():
    print()
    print("╔════════════════════════════════════════════╗")
    print(f"║         {GREEN}{BOLD}VERIFICATION PASSED{RESET}               ║")
    print("╚════════════════════════════════════════════╝")
    print()


def run(args, capture=True):
    """Run a manage.py command. Returns (returncode, stderr_text)."""
    cmd = [sys.executable, "manage.py"] + args
    if capture:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        return result.returncode, result.stderr
    else:
        result = subprocess.run(cmd)
        return result.returncode, ""


def main():
    header()

    # ── Preflight ───────────────────────────────────────────
    code, _ = run(["version"])
    if code != 0:
        print(f"  {CROSS} Cannot invoke Django.")
        print("    Please activate the project virtual environment first.")
        sys.exit(1)

    # ── Step 1: Django system check ─────────────────────────
    print("  [1/3] Django configuration")
    code, _ = run(["check"])
    if code != 0:
        print(f"        {CROSS} System check failed")
        run(["check"], capture=False)
        fail_footer()
        sys.exit(1)
    print(f"        {CHECK} System check passed")
    print()

    # ── Step 2: Migration state ─────────────────────────────
    print("  [2/3] Database state")
    code, _ = run(["migrate", "--check"])
    if code != 0:
        print(f"        {CROSS} Migrations are not applied")
        print("        Run: python manage.py migrate")
        fail_footer()
        sys.exit(1)
    print(f"        {CHECK} Migrations are up to date")
    print()

    # ── Step 3: Automated tests ─────────────────────────────
    print("  [3/3] Automated test suite")

    cmd = [sys.executable, "manage.py", "test", "--verbosity", "2"]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:
        for line in result.stderr.splitlines():
            if line.rstrip().endswith("... ok"):
                # Extract short test name (first token)
                name = line.split()[0] if line.split() else ""
                label = re.sub(r"^test_", "", name).replace("_", " ")
                print(f"        {CHECK} {label}")

        # Extract count from "Ran NN tests"
        match = re.search(r"Ran (\d+) tests?", result.stderr)
        count = match.group(1) if match else "?"

        print()
        print("        ────────────────────────────────────")
        print(f"        {CHECK} {BOLD}{count} tests passed{RESET}")
        pass_footer()
    else:
        print(f"        {CROSS} Test suite failed")
        print()
        print(result.stderr)
        fail_footer()
        sys.exit(1)


if __name__ == "__main__":
    main()
