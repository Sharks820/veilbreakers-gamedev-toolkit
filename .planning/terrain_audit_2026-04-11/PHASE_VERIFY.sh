#!/bin/bash
# Phase verification script — run after EVERY phase execution
# Usage: bash .planning/terrain_audit_2026-04-11/PHASE_VERIFY.sh [phase_number]

PHASE_NUM="${1:-49}"
cd "$(dirname "$0")/../../Tools/mcp-toolkit" || exit 1

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " PHASE ${PHASE_NUM} VERIFICATION GATE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FAILURES=0

# 1. Full test suite
echo ""
echo "[1/6] Running full test suite..."
TEST_OUTPUT=$(python -m pytest tests/ -q --tb=line 2>&1)
TEST_RESULT=$?
PASSED=$(echo "$TEST_OUTPUT" | grep -oP '\d+ passed' | grep -oP '\d+')
FAILED=$(echo "$TEST_OUTPUT" | grep -oP '\d+ failed' | grep -oP '\d+')
ERRORS=$(echo "$TEST_OUTPUT" | grep -oP '\d+ error' | grep -oP '\d+')
echo "  Passed: ${PASSED:-0} | Failed: ${FAILED:-0} | Errors: ${ERRORS:-0}"
if [ "${FAILED:-0}" -gt 0 ] || [ "${ERRORS:-0}" -gt 0 ]; then
    echo "  FAIL: Tests have failures/errors"
    FAILURES=$((FAILURES + 1))
else
    echo "  PASS"
fi

# 2. Quality lint
echo ""
echo "[2/6] Running quality_lint..."
LINT_OUTPUT=$(python scripts/quality_lint.py blender_addon/handlers/ 2>&1)
LINT_COUNT=$(echo "$LINT_OUTPUT" | grep -oP '\d+ finding' | grep -oP '\d+' | head -1)
echo "  Findings: ${LINT_COUNT:-0}"
if [ "${LINT_COUNT:-0}" -gt 16 ]; then
    echo "  FAIL: Lint findings > 16 ceiling"
    FAILURES=$((FAILURES + 1))
else
    echo "  PASS"
fi

# 3. Test substance lint
echo ""
echo "[3/6] Running test_substance_lint..."
SUBSTANCE_OUTPUT=$(python scripts/test_substance_lint.py tests/ 2>&1)
REAL_RATIO=$(echo "$SUBSTANCE_OUTPUT" | grep -oP 'real_ratio.*?(\d+\.\d+)' | grep -oP '\d+\.\d+' | tail -1)
echo "  Real ratio: ${REAL_RATIO:-unknown}"

# 4. Import chain
echo ""
echo "[4/6] Checking import chain..."
IMPORT_OUTPUT=$(python -c "from blender_addon.handlers.terrain_master_registrar import register_all_terrain_passes; print('OK')" 2>&1)
if echo "$IMPORT_OUTPUT" | grep -q "OK"; then
    echo "  PASS"
else
    echo "  FAIL: Import chain broken"
    FAILURES=$((FAILURES + 1))
fi

# 5. Code reviewer (advisory)
echo ""
echo "[5/6] Running code reviewer (advisory)..."
REVIEWER_OUTPUT=$(PYTHONPATH=src python src/veilbreakers_mcp/vb_code_reviewer.py blender_addon/handlers/ --scope advisory --profile blender 2>&1 | tail -5)
echo "  $REVIEWER_OUTPUT"

# 6. Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$FAILURES" -eq 0 ]; then
    echo " PHASE ${PHASE_NUM} VERIFICATION: PASSED"
else
    echo " PHASE ${PHASE_NUM} VERIFICATION: FAILED ($FAILURES gates)"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit $FAILURES
