#!/usr/bin/env bash
# Build and run the self-contained examples as a regression test.
#
#   ./examples/run_all.sh 10_6     # the CMSSW_10_6_30 package
#   ./examples/run_all.sh 20_1     # the CMSSW_20_1_0_pre4 package
#   ./examples/run_all.sh 20_1 MuonGunSim MuonGunDigi   # just these
#
# Run this from inside the matching dev shell. The job list lives in
# examples/jobs.json, which `nix flake check` reads too - see the checks in
# flake.nix, which run the same jobs hermetically. This script is the
# interactive counterpart: it builds in the working tree, so an edit to an
# example is one `cmake --build` away from being tested.
set -u

era=${1:-20_1}
shift || true
only=" $* "   # example directories to run; all of them if none given
case "$era" in
  10_6) attr=cmssw_10_6_30 ;;
  20_1) attr=cmssw ;;
  *) echo "usage: $0 [10_6|20_1]" >&2; exit 2 ;;
esac

here=$(cd "$(dirname "$0")" && pwd)

# "<dir>:<cfg>" per line, in the order jobs.json lists them
mapfile -t jobs < <(python3 -c '
import json, sys
era = sys.argv[1]
with open(sys.argv[2]) as f:
    spec = json.load(f)
only = sys.argv[3].split()
for job in spec[era]:
    if only and job["dir"] not in only:
        continue
    for cfg in job["cfgs"]:
        print(job["dir"] + ":" + cfg)
' "$era" "$here/jobs.json" "$only") || { echo "cannot read $here/jobs.json" >&2; exit 2; }
[ ${#jobs[@]} -gt 0 ] || { echo "no example jobs match:$only" >&2; exit 2; }

# A build directory of its own per release: the two eras have different
# compilers and a different TBB, and a CMakeCache left behind by the other
# one silently builds against the wrong toolchain. (scripts/worktree.sh sets
# RUN_ALL_BUILD_DIR, for the same reason, to keep a work tree's release
# apart from the nix-built one.)
run_one() {
  local dir=$1 cfg=$2 bld=${RUN_ALL_BUILD_DIR:-build-$era}
  echo "=== $dir : $cfg"
  ( cd "$here/$dir" || exit 1
    cmake -B "$bld" -S . -G Ninja > build.log 2>&1 || { echo "   CMAKE FAILED"; tail -5 build.log; exit 1; }
    cmake --build "$bld" >> build.log 2>&1 || { echo "   BUILD FAILED"; grep -m5 "error:" build.log; exit 1; }
    export LD_LIBRARY_PATH=$PWD/$bld:${LD_LIBRARY_PATH:-}
    edmPluginRefresh "$PWD/$bld" > /dev/null 2>&1
    cmsRun "$cfg" > run.log 2>&1 || { echo "   RUN FAILED"; tail -25 run.log; exit 1; }
    # an optional <cfg>_check.py validates the job output from outside
    # CMSSW (e.g. reading a produced nanoAOD file with plain ROOT)
    if [ -f "${cfg%.py}_check.py" ]; then
      python3 "${cfg%.py}_check.py" > check.log 2>&1 || { echo "   CHECK FAILED"; tail -15 check.log; exit 1; }
    fi
    echo "   ok" )
}

fail=0
for job in "${jobs[@]}"; do
  run_one "${job%%:*}" "${job#*:}" || fail=$((fail + 1))
done

echo
if [ "$fail" -eq 0 ]; then
  echo "all ${#jobs[@]} example jobs passed ($attr)"
else
  echo "$fail of ${#jobs[@]} example jobs FAILED ($attr)"
fi
exit $fail
