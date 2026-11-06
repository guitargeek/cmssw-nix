#!/usr/bin/env bash
# The whole chain for real: 10 events through all four steps, conditions
# from the global tag over Frontier (network access to cmsfrontier.cern.ch),
# then a look at the NanoAOD with plain ROOT. Run it from the dev shell with
# the cms-data (nix develop .#with-reco-data), in a directory of your
# choice; it takes a few minutes on a laptop.
#
#   examples/CmsDriverChain/run_chain.sh [workdir]
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
work=${1:-$PWD/cmsdriver-chain}
mkdir -p "$work"
cd "$work"
for step in 1 2 3 4; do
  cfg=step${step}_cfg.py
  echo "=== step $step ($cfg)"
  python3 "$here/python/chain.py" $step > "step$step.driver.log" 2>&1 || { cat "step$step.driver.log"; exit 1; }
  # A Fortran STOP in a generator library ends the process with status 0:
  # the output file is the real success criterion.
  cmsRun "$cfg" > "step$step.log" 2>&1 || { tail -30 "step$step.log"; exit 1; }
done
for f in step1.root step2.root step3.root step3_inMINIAODSIM.root step4.root; do
  [ -f "$f" ] || { echo "missing $f"; exit 1; }
done
python3 "$here/python/nano_check.py" step4.root
