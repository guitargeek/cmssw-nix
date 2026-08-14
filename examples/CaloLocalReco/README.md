# CaloLocalReco

Runs the CMSSW calorimeter local reconstruction on toy digis with the
`CMSSW_10_6_30` package of this flake: Ecal weights-method uncalibrated and
calibrated rec hits, the phase-1 HBHE reconstructor (Mahi + M0), and the
calo-tower creator. Everything is self-contained:

* the `CaloGeometry` is built at runtime from the DDD XML detector
  description (the 2016 geometry filtered to the world/envelope volumes and
  the Ecal + Hcal subdetectors),
* all Ecal conditions come from the `EcalTrivialConditionRetriever`, all
  Hcal conditions from the `HcalHardcodeCalibrations` ES source,
* a toy producer places a pulse on a 2×2 block of EB crystals and on one HB
  cell that map to the *same* calo tower (ieta 1, iphi 1).

A checker module asserts that exactly four EB rec hits, one HBHE rec hit
and one calo tower with both EM and HAD energy come out — so the chain is
only complete if the rec hits, the tower constituents mapping and the
severity-level machinery all work.

This example needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`).

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30`:

```bash
cmake -B build -S . -G Ninja
cmake --build build

# register the plugins so cmsRun can find them
export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

cmsRun python/calo_localreco_cfg.py
```

Expected output:

```
toy digis: 2x2 EB crystals around 838926859 (ieta 1, iphi 11), HB cell 1125647361 (ieta 1, iphi 1, depth 1)
geometry: 61200 EB cells, 2592 HB cells, 4320 tower cells
EB rec hits: 4, HBHE rec hits: 1, calo towers: 1
calo tower (ieta 1, iphi 1): em = 27.8613 GeV, had = 669.194 GeV
```

The job fails (non-zero exit) on any other outcome, so it doubles as a
regression test for the calo geometry/conditions/local-reco slice of the
build.

## Notes on the configuration

* The XML file list comes from `cmsExtendedGeometry2016XML_cfi`, filtered
  to `CMSCommonData` + `EcalCommonData` + `EcalSimData` (the `ReadOutName`
  spec-pars the Ecal geometry loader filters on) + `HcalCommonData`. A few
  world-detail files (beam pipe, cavern, muon barrel content) must also be
  dropped: they position volumes whose definitions live in the dropped
  subdetector files, and the resulting ghost logical parts crash the DDD
  spec-par scan.
* The Hcal DDD constants/topology ES producers and the Hcal severity-level
  computer are declared inline — their cfi files are scram-generated and
  not part of this build.
* `data/*_SimPulseShape.txt` are the EB/EE pulse shapes extracted from the
  hardcoded arrays in `SimCalorimetry/EcalSimAlgos` (the trivial retriever
  wants them as text files; in production this payload comes from the
  conditions DB).
* Method 3 (`useM3=False`) and the HBHE negative-energy filter
  (`setNegativeFlagsQIE8=False`) are off: their payloads only exist in the
  conditions DB.
* The toy EB deposit is a 2×2 crystal block: a single crystal would be
  flagged as a spike (`kWeird`) by the swiss-cross topology check and
  correctly excluded from the towers. Barrel crystals iphi 11–15 belong to
  tower iphi 1 (the crystal numbering is offset by 70 in phi).
