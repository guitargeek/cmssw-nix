#!/usr/bin/env bash
# Iterate on a CMSSW release with incremental builds instead of `nix build`.
#
#   scripts/worktree.sh <era> <command> [args]
#
#   era:  20_1 | 10_6
#
#   env                  (re)generate the build environment from the flake;
#                        after changing flake.nix, flake.lock or pkgs/ (then
#                        `configure --fresh`)
#   fresh                unpack, patch (incl. the serialization code
#                        generation) and configure a new tree from scratch
#   sync                 apply edits to gen/ (prepare_sources.py, config.yml,
#                        CMakeLists.txt, the generator) to the existing tree:
#                        re-prepares a fresh copy and copies over only the
#                        files whose content changed, then re-runs configure
#   configure [--fresh]  re-run the configure phase; --fresh drops the CMake
#                        cache first (needed when dependencies changed)
#   build [target...]    incremental build (-k 0: report every broken target);
#                        with targets, build only those (e.g.
#                        lib/libFWCoreFramework.so)
#   install              run the install phase into <tree>/out: install, plugin
#                        cache (every plugin is loaded), cfi generation
#   run [example...]     build the examples against <tree>/out and run their
#                        jobs (examples/run_all.sh; default: all of them)
#   shell                interactive shell with <tree>/out as the release
#
# The tree lives in ${CMSSW_WORKTREE:-<repo>/worktree}/<era> (gitignored).
# Every command runs the derivation's own phases from pkgs/cmssw.nix in the
# environment `nix print-dev-env` gives for the package, so what builds here
# builds in the sandbox - but `nix build` remains the reference: run it (and
# `nix flake check`) once the tree is green.
set -euo pipefail

if [ "${BASH_VERSINFO[0]}" -lt 4 ]; then
  # the printed environment needs a modern bash (macOS ships 3.2)
  echo "worktree.sh needs bash >= 4 (try: nix shell nixpkgs#bash -c $0 $*)" >&2
  exit 2
fi

usage() { sed -n '2,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 2; }

[ $# -ge 2 ] || usage
era=$1; cmd=$2; shift 2
case "$era" in
  20_1) attr=cmssw;         data=geant4-data_201 ;;
  10_6) attr=cmssw_10_6_30; data=geant4-data ;;
  *) usage ;;
esac

repo=$(cd "$(dirname "$0")/.." && pwd)
T=${CMSSW_WORKTREE:-$repo/worktree}/$era
# The physical path: the CondFormats serialization generator compares
# resolved file paths against CMSSW_BASE=$PWD, so a symlink anywhere in the
# tree's path (macOS's /tmp is one) would break the patch phase.
mkdir -p "$T"; T=$(cd "$T" && pwd -P)
src=$T/cmssw-build-root
system=$(nix eval --impure --raw --expr builtins.currentSystem)
cores=${CORES:-$(getconf _NPROCESSORS_ONLN)}

# Run a bash snippet in the release's build environment, with $out pointing
# into the tree.
in_env() {
  [ -f "$T/env.sh" ] || { echo "no environment yet: run '$0 $era env' first" >&2; exit 1; }
  "$BASH" -c "source '$T/env.sh' > /dev/null
              export out='$T/out' NIX_BUILD_CORES='$cores'
              set -e
              $1"
}

# Run one of the derivation's phases in the tree. The overridden phases are
# strings to eval; the stdenv ones (unpackPhase, patchPhase) are functions.
phase() {
  in_env "cd '$src' && if [ -n \"\${$1:-}\" ]; then eval \"\${$1}\"; else $1; fi"
}

# Remove a directory that may contain read-only files copied from the store.
remove() {
  [ -e "$1" ] || return 0
  chmod -R u+w "$1" && rm -rf "$1"
}

# Unpack and patch a fresh copy of the sources into $1.
prepare_into() {
  remove "$1"; mkdir -p "$1"
  in_env "cd '$1' && unpackPhase > unpack.log 2>&1 && cd \"\$sourceRoot\" && patchPhase > ../patch.log 2>&1" \
    || { echo "unpack/patch failed, see $1/patch.log" >&2; exit 1; }
}

# The phases in the printed environment refer to gen/ by store path, as of
# when it was printed: an edit to prepare_sources.py reaches the tree only
# through a new environment. Cheap when the dependencies are unchanged.
make_env() {
  echo "==> build environment of .#packages.$system.$attr"
  nix print-dev-env "$repo#packages.$system.$attr" > "$T/env.sh.new"
  mv "$T/env.sh.new" "$T/env.sh"
  # the examples need the Geant4 datasets on top (see extraPackages_* in
  # flake.nix; everything else there is part of the build environment)
  nix build --no-link --print-out-paths "$repo#packages.$system.$data" > "$T/data.path"
}

case "$cmd" in
  env)
    make_env
    echo "environment written to $T/env.sh"
    ;;

  fresh)
    make_env
    remove "$src"; remove "$T/out"
    mkdir -p "$T"
    echo "==> unpack + patch (generates the CondFormats serialization code; takes a while)"
    in_env "cd '$T' && unpackPhase > unpack.log 2>&1 && cd \"\$sourceRoot\" && patchPhase > ../patch.log 2>&1" \
      || { echo "unpack/patch failed, see $T/patch.log" >&2; exit 1; }
    echo "==> configure"
    phase configurePhase > "$T/configure.log" 2>&1 || { tail -20 "$T/configure.log"; exit 1; }
    echo "configured; next: $0 $era build"
    ;;

  sync)
    [ -d "$src" ] || { echo "no tree yet: run '$0 $era fresh'" >&2; exit 1; }
    make_env
    # prepare_sources.py edits the sources in place and is not idempotent,
    # so it must never run on the tree itself. Prepare a fresh copy and copy
    # over what differs by content: unchanged files keep their mtimes, so
    # ninja rebuilds only what the edit touched.
    echo "==> preparing a fresh copy"
    prepare_into "$T/.sync"
    in_env "python3 - '$T/.sync/cmssw-build-root' '$src'" <<'EOF'
import filecmp, os, shutil, sys
new, tree = sys.argv[1], sys.argv[2]
changed = 0
for root, dirs, files in os.walk(new):
    rel = os.path.relpath(root, new)
    os.makedirs(os.path.join(tree, rel), exist_ok=True)
    for name in files:
        a, b = os.path.join(root, name), os.path.join(tree, rel, name)
        if os.path.islink(a) or not os.path.isfile(a):
            continue
        if os.path.isfile(b) and filecmp.cmp(a, b, shallow=False):
            continue
        if os.path.exists(b):
            os.chmod(b, 0o644)
        shutil.copyfile(a, b)
        changed += 1
        print("   ", os.path.normpath(os.path.join(rel, name)))
print(f"{changed} file(s) changed")
EOF
    remove "$T/.sync"
    echo "==> configure"
    phase configurePhase > "$T/configure.log" 2>&1 || { tail -20 "$T/configure.log"; exit 1; }
    echo "synced; next: $0 $era build"
    ;;

  configure)
    if [ "${1:-}" = --fresh ]; then rm -f "$src/build/CMakeCache.txt"; fi
    phase configurePhase > "$T/configure.log" 2>&1 || { tail -20 "$T/configure.log"; exit 1; }
    echo "configured"
    ;;

  build)
    log=$T/build.log
    if [ $# -gt 0 ]; then
      in_env "cd '$src/build' && ninja -k 0 $*" 2>&1 | tee "$log" | grep -E '^\[[0-9]+/|^FAILED' || true
    else
      phase buildPhase > "$log" 2>&1 || true
    fi
    n=$(grep -c '^FAILED' "$log" || true)
    if [ "$n" -gt 0 ]; then
      echo "$n target(s) failed, first errors (full log: $log):"
      grep -E ': error:' "$log" | sed "s|$src/||" | awk '!seen[$0]++' | head -20
      exit 1
    fi
    tail -1 "$log"
    ;;

  install)
    remove "$T/out"
    phase installPhase > "$T/install.log" 2>&1 \
      || { echo "install failed, see $T/install.log" >&2; tail -20 "$T/install.log"; exit 1; }
    echo "installed into $T/out ($(grep -c 'unable to load' "$src/plugin-refresh.log" || true) unloadable plugins)"
    ;;

  run|shell)
    [ -f "$T/out/nix-support/setup-hook" ] || { echo "nothing installed: run '$0 $era install'" >&2; exit 1; }
    rc=$T/shellrc
    cat > "$rc" <<EOF
source '$T/env.sh' > /dev/null
source '$T/out/nix-support/setup-hook'
source '$(cat "$T/data.path")/nix-support/setup-hook'
PS1='[worktree $era] \w \$ '
EOF
    if [ "$cmd" = shell ]; then
      exec "$BASH" --rcfile "$rc" -i
    fi
    # a build directory of its own, so the examples' CMake caches never mix
    # this tree's release with the nix-built one
    "$BASH" -c "source '$rc'; RUN_ALL_BUILD_DIR=build-$era-worktree exec '$BASH' '$repo/examples/run_all.sh' $era $*"
    ;;

  *) usage ;;
esac
