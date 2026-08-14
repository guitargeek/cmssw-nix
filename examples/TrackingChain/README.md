# TrackingChain

Runs the CMS tracking and vertexing chain on toy digis with the
`CMSSW_10_6_30` package of this flake: pixel/strip local reco,
pixel-triplet seeding, helix fitting and primary-vertex reconstruction —
the full path from raw-equivalent digis to `reco::Track`s and a
`reco::Vertex`.

The toy producer places digis along **true helices** (uniform 3.8 T
field): for each configured track it intersects the helix with every
barrel module plane of the XML-built `TrackerGeometry` (with a Newton
refinement onto the tilted module planes) and deposits pixel/strip digis
at the crossing points. Three tracks with different pt, phi, eta and
charge give 11 pixel and 42 strip hits.

The standard reconstruction then runs unchanged: clusterizers → rec hits
→ `SeedingLayersEDProducer` (2016 pixel-triplet layer sets) →
`HitPairEDProducer` → `PixelTripletHLTEDProducer` →
`PixelFitterByHelixProjections` → `PixelTrackProducer` →
`OfflinePrimaryVertices`. A checker asserts three reconstructed tracks
and a primary vertex containing all of them.

This example needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`).

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30`:

```bash
cmake -B build -S . -G Ninja
cmake --build build

export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

cmsRun python/tracking_chain_cfg.py
```

Expected output:

```
toy digis for 3 tracks: 11 pixel hits, 42 strip hits
reconstructed 3 tracks, 1 primary vertices
track: pt = ... eta = 0.248 ... phi = -2.397 ... hits = 3 ...
track: pt = ... eta = 0.151 ... phi = 0.295 ...
track: pt = ... eta = -0.099 ... phi = 1.796 ...
vertex: (-0.0076, 0.0091, 0.0055) with 3 tracks
```

The reconstructed phi/eta match the injected tracks; with only the three
pixel-barrel layers, the pt resolution is coarse (the layers span 10 cm,
so a 10 GeV track sags by ~50 μm across them). The job fails on any
other outcome, so it doubles as a regression test for the whole
tracking/vertexing slice of the build.

## The CKF chain

`python/ckf_chain_cfg.py` extends the same event through the full
**combinatorial Kalman filter**: seeds built from the pixel triplets
(`SeedCreatorFromRegionConsecutiveHitsEDProducer`, as production
`initialStepSeeds` does) are propagated through the strip detector by
`CkfTrackCandidateMaker` on the `MeasurementTrackerEvent`, and the
candidates are Kalman-fitted by the standard final fit
(`CTFFinalFitWithMaterial`) into `generalTracks`, from which
`OfflinePrimaryVertices` fits the vertex:

```
track: pt = 12.0519 GeV, eta = 0.2502, phi = -2.4003, q = 1, hits = 21, chi2/ndof = 0.85
track: pt = 5.0072 GeV,  eta = 0.1506, phi = 0.2997,  q = 1, hits = 16, chi2/ndof = 0.30
track: pt = 7.9803 GeV,  eta = -0.0999, phi = 1.7998, q = -1, hits = 16, chi2/ndof = 0.72
vertex: (-0.0023, -0.0132, -0.0004) with 3 tracks
```

With the strip hits in the fit the momenta match the injected values
(12, 5, 8 GeV) to a few permil, with the right charges. Two toy-specific
accommodations, commented in the config: the chi2 window is widened to
100 (the toy digis carry no Lorentz drift, which the CPEs correct for)
and lost-hit allowances are raised (stereo matching on glued layers can
fail for the sharing-free toy clusters). The pixel CPE runs template-free
and the measurement tracker skips the pixel-quality masking — both only
exist as conditions-DB payloads.

## Notes on the configuration

* The primary-vertex track filter is loosened to
  `minSiliconLayersWithHits = 3` — pixel tracks have exactly three
  layers, and the default of 5 silently rejects them all (the producer
  then emits a dummy vertex with zero tracks).
* `BeamSpotFakeConditions` is declared with the plugin's actual
  parameters (the shipped cfi predates them).
* The seeding/fitting modules are declared with their
  `fillDescriptions` defaults where the shipped cfi files import
  scram-generated ones (newer builds of this flake generate those
  cfipython files at install time via `edmWriteConfigs`, so plain
  `process.load(...)` works too).
