#!/usr/bin/env bash
set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
RED="\033[0;31m"
RESET="\033[0m"

echo ""
echo "========================================"
echo " Ahoum Events Platform — Verification"
echo "========================================"
echo ""

# Check that Django is available
if ! python manage.py version > /dev/null 2>&1; then
    echo -e "${RED}Error:${RESET} Cannot invoke Django."
    echo "Please activate the project virtual environment first."
    exit 1
fi

# Step 1 — Django system check
echo -n "[1/3] Django system check ... "
if python manage.py check --deploy 2>/dev/null || python manage.py check > /dev/null 2>&1; then
    python manage.py check > /dev/null 2>&1
    echo -e "${GREEN}PASS${RESET}"
else
    echo -e "${RED}FAIL${RESET}"
    echo ""
    echo "========================================"
    echo -e " ${RED}VERIFICATION FAILED${RESET}"
    echo "========================================"
    echo ""
    echo "Check the output above for the failing step."
    exit 1
fi

# Step 2 — Migration consistency check
echo -n "[2/3] Database migrations ... "
if python manage.py migrate --check > /dev/null 2>&1; then
    echo -e "${GREEN}PASS${RESET}"
else
    echo -e "${RED}FAIL${RESET}"
    echo ""
    echo "Migrations are not fully applied."
    echo "Run: python manage.py migrate"
    echo ""
    echo "========================================"
    echo -e " ${RED}VERIFICATION FAILED${RESET}"
    echo "========================================"
    exit 1
fi

# Step 3 — Automated tests
echo -n "[3/3] Automated tests ... "
TMPFILE=$(mktemp)
trap "rm -f '$TMPFILE'" EXIT

if python manage.py test 2>"$TMPFILE" 1>/dev/null; then
    # Extract the test count from stderr (Django writes test output to stderr)
    TEST_LINE=$(grep -oP 'Ran \d+ tests?' "$TMPFILE" || true)
    if [ -n "$TEST_LINE" ]; then
        COUNT=$(echo "$TEST_LINE" | grep -oP '\d+')
        echo -e "${GREEN}${COUNT} tests passed${RESET}"
    else
        echo -e "${GREEN}PASS${RESET}"
    fi
else
    echo -e "${RED}FAIL${RESET}"
    echo ""
    cat "$TMPFILE"
    echo ""
    echo "========================================"
    echo -e " ${RED}VERIFICATION FAILED${RESET}"
    echo "========================================"
    echo ""
    echo "Check the output above for the failing step."
    exit 1
fi

echo ""
echo "========================================"
echo -e " ${GREEN}${BOLD}VERIFICATION PASSED${RESET}"
echo "========================================"
echo ""
