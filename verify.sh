#!/usr/bin/env bash
set -e

# ── Colors ──────────────────────────────────────────────────
GREEN="\033[0;32m"
RED="\033[0;31m"
BOLD="\033[1m"
DIM="\033[2m"
RESET="\033[0m"
CHECK="${GREEN}✓${RESET}"
CROSS="${RED}✗${RESET}"

# ── Header ──────────────────────────────────────────────────
echo ""
echo "╔════════════════════════════════════════════╗"
echo "║       Ahoum Events Platform                ║"
echo "║       Backend Verification                 ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# ── Preflight ───────────────────────────────────────────────
if ! python manage.py version > /dev/null 2>&1; then
    echo -e "  ${CROSS} Cannot invoke Django."
    echo "    Please activate the project virtual environment first."
    exit 1
fi

# ── Step 1: Django system check ─────────────────────────────
echo -e "  [1/3] Django configuration"
if python manage.py check > /dev/null 2>&1; then
    echo -e "        ${CHECK} System check passed"
else
    echo -e "        ${CROSS} System check failed"
    echo ""
    python manage.py check
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo -e "║         ${RED}VERIFICATION FAILED${RESET}               ║"
    echo "╚════════════════════════════════════════════╝"
    exit 1
fi
echo ""

# ── Step 2: Migration state ─────────────────────────────────
echo -e "  [2/3] Database state"
if python manage.py migrate --check > /dev/null 2>&1; then
    echo -e "        ${CHECK} Migrations are up to date"
else
    echo -e "        ${CROSS} Migrations are not applied"
    echo "        Run: python manage.py migrate"
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo -e "║         ${RED}VERIFICATION FAILED${RESET}               ║"
    echo "╚════════════════════════════════════════════╝"
    exit 1
fi
echo ""

# ── Step 3: Automated tests (live progress) ─────────────────
echo -e "  [3/3] Automated test suite"

TMPFILE=$(mktemp)
trap "rm -f '$TMPFILE'" EXIT

# Run tests with verbosity 2 to get individual test names.
# Django writes test output to stderr.
if python manage.py test --verbosity 2 > /dev/null 2>"$TMPFILE"; then
    # Stream each test result from the captured output
    while IFS= read -r line; do
        # Lines look like: test_name (module.Class.test_name) ... ok
        if echo "$line" | grep -qP '\.\.\. ok$'; then
            # Extract the short test name (first word)
            NAME=$(echo "$line" | awk '{print $1}')
            # Make the name human-readable: test_otp_expires → otp expires
            LABEL=$(echo "$NAME" | sed 's/^test_//' | tr '_' ' ')
            echo -e "        ${CHECK} ${LABEL}"
        fi
    done < "$TMPFILE"

    # Extract the final count
    COUNT=$(grep -oP 'Ran \d+ tests?' "$TMPFILE" | grep -oP '\d+' || echo "?")

    echo ""
    echo "        ────────────────────────────────────"
    echo -e "        ${CHECK} ${BOLD}${COUNT} tests passed${RESET}"
else
    echo -e "        ${CROSS} Test suite failed"
    echo ""
    cat "$TMPFILE"
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo -e "║         ${RED}VERIFICATION FAILED${RESET}               ║"
    echo "╚════════════════════════════════════════════╝"
    exit 1
fi

# ── Footer ──────────────────────────────────────────────────
echo ""
echo "╔════════════════════════════════════════════╗"
echo -e "║         ${GREEN}${BOLD}VERIFICATION PASSED${RESET}               ║"
echo "╚════════════════════════════════════════════╝"
echo ""
