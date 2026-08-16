#!/usr/bin/env bash
# Build the releases and pin them against the garbage collector.
#
#   ./scripts/build.sh            # both releases
#   ./scripts/build.sh 10_6       # just one
#
# The out-links this creates (result-10_6, result-20_1) are indirect gcroots,
# so a later `nix-collect-garbage` cannot take a build that cost hours away.
# That is not automatic: a build you made with `nix build --no-link`, or one
# whose out-link you have since overwritten, is collectable the moment it is
# not referenced.
set -euo pipefail

cd "$(dirname "$0")/.."

# release : flake attribute
declare -A attrs=( [10_6]=cmssw_10_6_30 [20_1]=cmssw )

releases=("$@")
if [ ${#releases[@]} -eq 0 ]; then
  releases=(10_6 20_1)
fi

for rel in "${releases[@]}"; do
  attr=${attrs[$rel]:-}
  if [ -z "$attr" ]; then
    echo "unknown release '$rel' (known: ${!attrs[*]})" >&2
    exit 2
  fi
  echo "==> building .#$attr"
  nix build ".#$attr" --out-link "result-$rel" --print-build-logs
done

# The CMSSW checkouts are ~500 MB each and are not part of any output's runtime
# closure, so pinning the build does not pin them - they are the first thing a
# garbage collection takes and the slowest thing to fetch again. Root them
# explicitly.
echo "==> pinning sources"
for rel in "${releases[@]}"; do
  src=$(nix eval --raw ".#${attrs[$rel]}.src" 2>/dev/null) || continue
  nix-store --add-root "result-src-$rel" --indirect --realise "$src" > /dev/null
done

echo
for rel in "${releases[@]}"; do
  link="result-$rel"
  [ -L "$link" ] || continue
  printf '%-12s %s\n' "$rel" "$(readlink -f "$link")"
  nix path-info -Sh "$(readlink -f "$link")" | awk '{printf "%-12s closure %s %s\n", "", $2, $3}'
done
