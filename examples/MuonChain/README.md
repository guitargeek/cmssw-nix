# MuonChain

**Standalone muon reconstruction** on toy DT digis: digis → rec hits → 4D
segments → muon seed → a fitted `reco::Track` in the muon system, with the
`CMSSW_10_6_30` package of this flake.

This is the step the uniform 3.8 T field of the other examples cannot do. A
standalone muon is fitted entirely outside the solenoid, where the flux has
returned through the yoke iron and points the *other* way (see
[examples/MagneticFieldMap](../MagneticFieldMap)); under a uniform field the
trajectory propagation is wrong from the first station onwards. Everything
here runs on the volume-based field.

The toy muon is not a straight line either. `ToyMuonTrackDigiProducer` steps a
muon of a given `pt` out of the origin through the **same field the
reconstruction will use**, querying it from the EventSetup and integrating the
equation of motion with RK4; every DT layer the trajectory crosses gets a digi
on the wire the crossing lands on, with the drift time it implies. That is
what makes this a test of the field rather than only of the fit: a straight
track would come back out under any field, whereas this curvature is the one
the return flux produces.

Which chambers get hit is left to the trajectory — a muon of a few tens of
GeV bends by an appreciable fraction of a sector on its way out, so the
producer tests every chamber for a crossing instead of assuming the one it was
aimed at.

This example needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`).

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30`:

```bash
cmake -B build -S . -G Ninja
cmake --build build

export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

cmsRun python/muon_sta_cfg.py
```

Expected output:

```
muon pt = 50 GeV, charge 1, along (0.995907, 0.0903575, 0.00196329): 32 DT digis in wheel 0 sector 1, crossing 4 chambers
muon seeds: 1, standalone muons: 1
  standalone muon: pt = 54.6151 GeV, eta = 0.00148607, phi = 0.0850966, charge = 1, hits = 32, chi2/ndof = 0.0335844
```

All 32 digis end up on the track, the charge and direction are the injected
ones (φ = 0.085 against 0.090 generated), and the fit is good.

**The 50 GeV muon comes back as 55 GeV, and that is expected**: the fit
corrects for the energy a muon loses traversing the yoke iron on the way out,
which is about 4–5 GeV and which the toy does not simulate. The offset is
roughly constant in pt (20 GeV → 24, 50 → 55, 200 → 193), so it dominates at
low pt and is negligible at high pt. The checker therefore accepts a window
rather than a point, and fails the job if the track is missing, the charge is
wrong, or the pt is outside it.

## Notes on the configuration

* the standalone fit needs more of the detector than the muon local reco
  does: `TrackerTopology` (the track loader fills the `reco::Track` hit
  pattern through it) and the tracker *reco* geometry, because the
  `GlobalDetLayerGeometry` the KF fitters navigate on spans tracker and muon.
  Both are built from the same 2016 XML; no tracker hits are involved.
* CSC and RPC measurements are switched off in the seed generator and in both
  filters of the trajectory builder, since this event only has DT digis.
* a beam spot at the origin comes from `BeamSpotFakeConditions` plus the
  standard producer, as in [examples/TrackingChain](../TrackingChain).

Two things the toy has to get right for the fit to make sense, both of which
showed up as absurd χ² until they were fixed:

* the drift time has to include the **time of flight** from the vertex, since
  `DTTTrigSyncTOFCorr` subtracts it again during reconstruction (it differs by
  ~8 ns between the innermost and outermost station),
* a crossing further from the wire than half a cell is not in that cell, and
  writing a digi for it anyway puts hits where the track never went.
