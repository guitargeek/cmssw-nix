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

# release : dev shell attribute (the shells are named after the release for
# 10_6 and "default" for 20_1, which is not guessable from the release name)
declare -A shells=( [10_6]=cmssw_10_6_30 [20_1]=default )

releases=("$@")
if [ ${#releases[@]} -eq 0 ]; then
  releases=(10_6 20_1)
fi

# Check every argument before building anything. These builds are hours, and
# the loop below used to validate each release as it reached it - so
# `build.sh 20_1 --print-build-logs` (the flag is already passed internally)
# built 20_1 in full and only then rejected the second "release", after which
# the source pinning at the end never ran.
for rel in "${releases[@]}"; do
  if [ -z "${attrs[$rel]:-}" ]; then
    echo "unknown release '$rel' (known: ${!attrs[*]})" >&2
    exit 2
  fi
done

for rel in "${releases[@]}"; do
  echo "==> building .#${attrs[$rel]}"
  nix build ".#${attrs[$rel]}" --out-link "result-$rel" --print-build-logs
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

# The dev shells are what anything actually runs in, and their closure is not
# the release's. Geant4's datasets are the clearest case: they are in the
# shell, and in no package's runtime closure, so pinning the releases leaves
# them collectable. result-geant4 and result-g4data used to stand in for this
# by hand and had quietly gone dangling. mkShell's inputDerivation is the
# supported way to root a shell's inputs, and building it is cheap - the
# inputs are already realised, it only writes a file that refers to them.
echo "==> pinning dev shells"
system=$(nix eval --impure --raw --expr builtins.currentSystem)
for rel in "${releases[@]}"; do
  nix build ".#devShells.$system.${shells[$rel]}.inputDerivation" \
    --out-link "result-shell-$rel" || echo "  could not pin the $rel dev shell" >&2
done

echo
for rel in "${releases[@]}"; do
  link="result-$rel"
  [ -L "$link" ] || continue
  printf '%-12s %s\n' "$rel" "$(readlink -f "$link")"
  nix path-info -Sh "$(readlink -f "$link")" | awk '{printf "%-12s closure %s %s\n", "", $2, $3}'
done
