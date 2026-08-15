#!/usr/bin/env bash
# Build and run the self-contained examples as a regression test.
#
#   ./examples/run_all.sh 10_6     # the CMSSW_10_6_30 package
#   ./examples/run_all.sh 20_1     # the CMSSW_20_1_0_pre2 package
#
# Only the examples that need no external data are run; MiniAODReader needs a
# CMS Open Data file and is left out.
set -u

era=${1:-20_1}
case "$era" in
  10_6) attr=cmssw_10_6_30 ;;
  20_1) attr=cmssw ;;
  *) echo "usage: $0 [10_6|20_1]" >&2; exit 2 ;;
esac

here=$(cd "$(dirname "$0")" && pwd)

# example directory : config to run (relative to the example directory)
if [ "$era" = 10_6 ]; then
  jobs=(
    "MyAnalyzer:python/write_cfg.py"
    "MyAnalyzer:python/read_cfg.py"
    "TrackerLocalReco:python/tracker_localreco_cfg.py"
    "CaloLocalReco:python/calo_localreco_cfg.py"
    "MuonLocalReco:python/muon_localreco_cfg.py"
    "TrackingChain:python/tracking_chain_cfg.py"
    "TrackingChain:python/ckf_chain_cfg.py"
    "MagneticFieldMap:python/magfield_cfg.py"
    "MuonChain:python/muon_sta_cfg.py"
  )
else
  jobs=(
    "MyAnalyzer:python/write_cfg.py"
    "MyAnalyzer:python/read_cfg.py"
    "TrackerLocalReco:python/tracker_localreco_20_1_cfg.py"
  )
fi

# A build directory of its own per release: the two eras have different
# compilers and a different TBB, and a CMakeCache left behind by the other
# one silently builds against the wrong toolchain.
run_one() {
  local dir=$1 cfg=$2 bld="build-$era"
  echo "=== $dir : $cfg"
  ( cd "$here/$dir" || exit 1
    cmake -B "$bld" -S . -G Ninja > build.log 2>&1 || { echo "   CMAKE FAILED"; tail -5 build.log; exit 1; }
    cmake --build "$bld" >> build.log 2>&1 || { echo "   BUILD FAILED"; grep -m5 "error:" build.log; exit 1; }
    export LD_LIBRARY_PATH=$PWD/$bld:${LD_LIBRARY_PATH:-}
    edmPluginRefresh "$PWD/$bld" > /dev/null 2>&1
    cmsRun "$cfg" > run.log 2>&1 || { echo "   RUN FAILED"; tail -25 run.log; exit 1; }
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
