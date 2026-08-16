# TrackerLocalReco

Runs the CMSSW tracker local reconstruction — the SiStrip/SiPixel
clusterizers and rec-hit converters — on toy digis, with the
`CMSSW_10_6_30` package of this flake. Everything is self-contained:

* the `TrackerGeometry` is built at runtime from the DDD XML detector
  description (the 2016 geometry, filtered down to the world/envelope
  volumes and the tracker),
* all conditions (noise, gains, quality, cabling, Lorentz angles, ...)
  come from the fake "from parameters" ES sources in `CalibTracker`,
* a toy producer places three adjacent strip digis on the first TIB module
  and a 2×2 pixel block on the first pixel-barrel module of that geometry.

The standard `ThreeThresholdAlgorithm` strip clusterizer, the
`PixelThresholdClusterizer`, the `StripCPEfromTrackAngle` and the
`PixelCPEGeneric` (without template payloads) then run exactly as they
would in production, and a checker module asserts that precisely one
cluster and one rec hit per subdetector come out.

This example needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`).

A port to `CMSSW_20_1_0_pre2` is drafted in
`python/tracker_localreco_20_1_cfg.py` but **does not work yet** — see the
header of that file for the open issues.

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30`:

```bash
cmake -B build -S . -G Ninja
cmake --build build

# register the plugins so cmsRun can find them
export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

cmsRun python/tracker_localreco_cfg.py
```

Expected output:

```
toy digis: 3 strip digis on 369120278, 4 pixel digis on 302055684
strip clusters: 1, pixel clusters: 1, strip rec hits: 1, pixel rec hits: 1
strip hit on 369120278 at local x = -2.25925 +- 0.0023094
pixel hit on 302055684 at local (x, y) = (-0.60574, -2.76)
```

The job fails (non-zero exit) if the counts differ, so it doubles as a
regression test for the geometry/conditions/local-reco slice of the build.

## Notes on the configuration

The config wires up by hand what a release would get from
`Configuration/StandardSequences` and the scram-generated cfi files
(neither is part of this build):

* the XML file list is taken from `cmsExtendedGeometry2016XML_cfi` and
  filtered to `Geometry/CMSCommonData` + `Geometry/TrackerCommonData` —
  subdetector files only position volumes *into* the envelopes, so the
  calo/muon/forward files can be dropped without leaving dangling
  references (the shipped `testGeometryXML_cfi` is stale in 10_6),
* `SiStripDetInfoFileReader` is a framework *service* that every fake
  SiStrip ES source needs,
* the clusterizer requires the `SiStripQuality` object to carry the det
  cabling, so the real `SiStripQualityESProducer` is used (merging the
  fake cabling and bad-channel records) instead of the fake quality source,
* the strip CPE reads the latency-dependent Lorentz-angle/back-plane
  records (fakes cloned with the `peak`/`deconvolution` labels) and
  requires per-module-geometry cross-talk constants in the
  `SiStripConfObject` (generated with representative values),
* the pixel side runs without any template payloads
  (`UseErrorsFromTemplates=False` etc.) and with a plain
  ADC-to-electrons conversion (`MissCalibrate=False`), under a uniform
  3.8 T magnetic field.
