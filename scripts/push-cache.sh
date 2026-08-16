#!/usr/bin/env bash
# Push the built releases and everything they were built from to a cachix
# binary cache, so a second machine (or a fresh clone after a garbage
# collection) substitutes them instead of spending hours compiling.
#
#   export CACHIX_CACHE=my-cmssw-cache
#   export CACHIX_AUTH_TOKEN=...          # from `cachix authtoken`
#   ./scripts/push-cache.sh
#
# One-time setup, on any machine that has a cachix account:
#
#   nix run nixpkgs#cachix -- authtoken <token>
#   nix run nixpkgs#cachix -- create $CACHIX_CACHE
#
# To consume the cache afterwards, on the machine that wants the binaries:
#
#   nix run nixpkgs#cachix -- use $CACHIX_CACHE
#
# This flake deliberately does not put the cache in nixConfig: a substituter
# baked into the flake is a trust decision for whoever clones it, and an
# unreachable one makes every build print warnings.
set -euo pipefail

cd "$(dirname "$0")/.."

: "${CACHIX_CACHE:?set CACHIX_CACHE to the name of your cachix cache}"

cachix() { nix run nixpkgs#cachix -- "$@"; }

paths=()
for link in result-10_6 result-20_1; do
  [ -L "$link" ] || { echo "no $link - run ./scripts/build.sh first" >&2; exit 1; }
  paths+=("$(readlink -f "$link")")
done

# The runtime closure alone is not enough to make a rebuild cheap: a rebuild
# starts from the *build* inputs (compilers, ROOT, the generated sources), and
# those are what take the hours. Push the build closure too.
echo "==> pushing runtime closures"
cachix push "$CACHIX_CACHE" "${paths[@]}"

echo "==> pushing build-time closures"
derivers=()
for p in "${paths[@]}"; do
  derivers+=("$(nix-store --query --deriver "$p")")
done
nix-store --query --requisites --include-outputs "${derivers[@]}" \
  | grep -v '\.drv$' \
  | cachix push "$CACHIX_CACHE"

echo "done - consumers need: cachix use $CACHIX_CACHE"
