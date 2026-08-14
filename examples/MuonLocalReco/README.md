# MuonLocalReco

Runs the CMSSW muon local reconstruction on toy digis with the
`CMSSW_10_6_30` package of this flake: DT rec hits and 4D segments, CSC
rec hits and segments, and RPC rec hits. Everything is self-contained:

* the DT/CSC/RPC geometries are built at runtime from the DDD XML detector
  description (the 2016 geometry filtered to the world/envelope volumes,
  the muon system, and the reco spec-par files of the geometry builders),
* the CSC gains/pedestals/noise/crosstalk come from the fake ES sources in
  `CalibMuon/CSCCalibration`; DT runs with the constant-drift-velocity
  algorithm and the parameter-based TOF synchronization, RPC with the
  packaged mask/dead-strip files — no conditions DB anywhere,
* a toy producer places straight-track-like digis in one DT chamber
  (4 hits in each phi superlayer), one CSC chamber (strip + wire digis on
  4 layers of ME1/1) and the first barrel RPC roll of the geometry.

A checker module asserts eight DT rec hits + one 4D segment, four CSC rec
hits + one segment, and one RPC rec hit — so the example doubles as a
regression test for the muon geometry/conditions/local-reco slice.

This example needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`).

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30`:

```bash
cmake -B build -S . -G Ninja
cmake --build build

# register the plugins so cmsRun can find them
export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

cmsRun python/muon_localreco_cfg.py
```

Expected output:

```
geometry: 250 DT chambers, 612 CSC chambers, 2748 RPC rolls
toy digis: 8 DT (Wh0/St1/Sec1 SL1+SL3), 12 CSC strip + 4 wire (ME1/1), 2 RPC strips in  Re 0 Ri -2 St 1 Se 1 La 1 Su 1 Ro 1 Tr 0
DT rec hits: 8, DT 4D segments: 1, CSC rec hits: 4, CSC segments: 1, RPC rec hits: 1
DT 4D segment in  Wh:0 St:1 Se:1 : local pos (-63.53, 0), dir (0.000272423, 0)
CSC segment in  E:1 S:1 R:1 C:1 L:0: 4 hits, local pos (-0.250911, -11.4732)
RPC rec hit in  Re 0 Ri -2 St 1 Se 1 La 1 Su 1 Ro 1 Tr 0 : local x = -11.4444
```

## Notes on the configuration

* The XML file list is the 2016 one filtered to `CMSCommonData` +
  `MuonCommonData` + `MuonSimData` + the `*GeometryBuilder` data files —
  the latter carry the `MuStructure` spec-pars the DT/CSC/RPC geometry
  builders filter on; without them the builders throw "Failed to build the
  necessary objects from the DDD".
* The DT rec-hit and segment algorithms are the `LinearDrift` variants
  with `DTTTrigSyncTOFCorr` (fixed tTrig, no DB). The LinearDrift cfi
  files are missing the `perform_delta_rejecting` parameter of the
  maintained FromDB variants — it is added by hand.
* The CSC bad-channel lists and timing/gas-gain corrections exist only as
  conditions-DB payloads and are switched off.
