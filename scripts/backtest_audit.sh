#!/usr/bin/env sh
# Run the current audit suite against an older tag, with that tag's own code
# and sample corpus, to see which checks would have fired there.
#
#   scripts/backtest_audit.sh v1.0.0
#
# Legs that need the generators (repeat stress) are skipped automatically on
# tags that predate x12sdk.generate.
set -eu
tag="${1:?usage: scripts/backtest_audit.sh <tag>}"
root="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)/x12sdk-$tag"

git -C "$root" worktree add -q --detach "$work" "$tag"
trap 'git -C "$root" worktree remove --force "$work"' EXIT

rm -rf "$work/src/tests/audit"
cp -R "$root/src/tests/audit" "$work/src/tests/audit"

legs="test_structural.py test_construction.py test_mutation.py"
if [ -d "$work/src/x12sdk/generate" ]; then
  legs="$legs test_repeat_stress.py"
else
  echo "note: $tag has no x12sdk.generate; repeat-stress leg skipped"
fi

cd "$work"
PYTHONPATH="$work/src" python -c 'import x12sdk; print("auditing x12sdk", x12sdk.__version__)'
for leg in $legs; do
  echo
  echo "== $leg against $tag =="
  PYTHONPATH="$work/src" python -m pytest "src/tests/audit/$leg" -q -p no:cacheprovider --rootdir="$work" -rf 2>&1 \
    | grep -E "^FAILED|passed|failed" || true
done
