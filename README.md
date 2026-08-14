# CMSSW on nix

A nix flake that packages a subset of [CMSSW](https://github.com/cms-sw/cmssw),
built with cmake instead of scram. Two release eras are provided:

* `CMSSW_20_1_0_pre2` (default) — against nixos-unstable
* `CMSSW_10_6_30` (the Run-2 ultra-legacy release) — against nixos-22.05,
  whose toolchain matches the release era (gcc 11 / C++17, ROOT 6.24, classic
  TBB 2020.3 with the `tbb::task` API, python 3.9)

It is the successor of the
[Arch Linux PKGBUILD experiment](../PKGBUILDs/cmssw): the
`BuildFile.xml` → `CMakeLists.txt` conversion script from there lives on in
[gen/cmssw_cmake.py](gen/cmssw_cmake.py), now driven by a nix derivation.

## What is included

Enough of CMSSW to run `cmsRun` with EDM ROOT file input and output and to
work with electron collections, i.e. the transitive closure of:

* `FWCore` (framework, plugin manager, python configuration, services, ...)
* `IOPool` + `FWStorage` (`PoolSource`, `PoolOutputModule`, storage layer)
* `DataFormats` up to `EgammaCandidates` (`reco::GsfElectron` & friends),
  including the ROOT/reflex dictionaries needed to read and write them

The package list is defined in [gen/config.yml](gen/config.yml)
([gen/config-10_6.yml](gen/config-10_6.yml) for the 10_6-era package layout,
where the storage code lives in `Utilities/StorageFactory`,
`IOPool/TFileAdaptor` and `FWCore/Catalog` instead of `FWStorage`); the exact
set of external dependencies is resolved in [gen/CMakeLists.txt](gen/CMakeLists.txt).
The 10_6 build additionally covers the remaining reco physics-object data
formats: muons, jets, MET, taus, b-tagging, particle flow, Ecal/Hcal rec hits
and digis, muon-chamber local reco (CSC/DT/GEM), L1/HLT trigger objects and
`reco::GenParticle` — everything needed to read the high-level content of a
Run-2 AOD event — plus `DataFormats/PatCandidates` and its closure (two
`CondFormats` packages, the `SimDataFormats` generator products with the
HepMC external, pileup summary, luminosity) and the CTPPS / forward-proton /
L1-stage-2 formats, so complete miniAOD event records can be read. This is
validated against a real file: a `RunIISummer20UL16MiniAODv2` MINIAODSIM
file from [CMS Open Data](https://opendata.cern.ch) (produced with
CMSSW_10_6_30 itself) reads cleanly — every branch, no dictionary warnings.
Files on `eospublic` can be fetched without xrootd through the portal's
HTTP proxy: `https://opendata.cern.ch/eos/opendata/<path>`.

On top of the data formats, the 10_6 build carries a first slice of the
reco-path toolchain (towards AOD → miniAOD → nanoAOD processing): the
`TrackingTools`/`MagneticField`/`RecoVertex` transient-track machinery, the
`CommonTools` utilities, the CORAL-free `CondFormats` payload classes with
their EventSetup records, FWLite (`edmDumpEventContent`, `edmFileUtil` and
`edmProvDump` work against real files), and the `DataFormats/NanoAOD` flat
tables.

**Conditions database access works in both releases**: CORAL (the LCG
relational database layer, from CMS's fork) is packaged in
[pkgs/coral.nix](pkgs/coral.nix) with its SQLite backend and service
plugins, and both releases build `CondCore` (CondDB, ESSources,
DBOutputService, the BeamSpot record plugins) against it. The
boost-serialization code for the `CondFormats` payload classes is generated
at build time by CMSSW's own libclang-based generator, exactly as scram
does it. Payloads can be written to and read from `sqlite_file:` databases
through `PoolDBOutputService` / `PoolDBESSource`. Oracle/Frontier access
(real GlobalTags from the grid) is not built.

The first reconstruction step itself is also covered for the tracker, the
calorimeters and the muon system. **Tracker local reco**: the SiPixel/SiStrip clusterizers,
the strip zero suppression and the rec-hit converters with their
cluster-parameter estimators, together with the infrastructure they stand
on — the `TrackerGeometry` built at runtime from the DDD XML detector
description (`DetectorDescription`, `XMLIdealGeometryESSource` and the
tracker geometry data files), the tracker cabling/quality/gain/noise ES
producers from `CalibTracker` including the fake ("from parameters")
conditions sources, and the uniform + volume-based magnetic field engines.
**Calorimeter local reco**: the Ecal uncalibrated/calibrated rec-hit
producers (weights method, plus the multifit workers), the phase-1 HBHE
reconstructor (Mahi, M0 and — thanks to a standalone Minuit2 built from
the ROOT sources — the method-2 pulse fit), the HF/HO reconstructors and
the calo-tower creator, on top of the calo geometry builders
(`CaloGeometry` from the same XML detector description) and the standalone
conditions providers (`EcalTrivialConditionRetriever`,
`HcalHardcodeCalibrations`). **Muon local reco**: DT rec hits and 4D
segments, CSC rec hits and segments and RPC rec hits, with the muon
geometries built from the same XML detector description and the fake
CSC calibrations / parameter-based DT synchronization instead of a
conditions DB.

All three chains are validated end-to-end without any external data: toy
digis placed on modules/cells of the XML-built geometries come out as
exactly the expected clusters, rec hits, segments and calo towers — see
[examples/TrackerLocalReco](examples/TrackerLocalReco),
[examples/CaloLocalReco](examples/CaloLocalReco) and
[examples/MuonLocalReco](examples/MuonLocalReco), which double as
regression tests.

Still out of scope for *producing* miniAOD/nanoAOD: the remaining
`PhysicsTools`/`RecoXyz` plugin packages and TensorFlow C++.
Everything comes from nixpkgs except two tiny CMS externals packaged here
(`cms-md5`, alpaka headers). For `CMSSW_20_1_0_pre2`, ROOT is rebuilt with
C++20 to match CMSSW; the ROOT 6.24 of nixos-22.05 is already C++17 and is
used as-is for `CMSSW_10_6_30`.

## Usage

```bash
nix build          # builds the cmssw package (takes a while!)
nix develop        # shell with cmsRun, CMSSW libs and headers, cmake, ROOT

# inside the shell, CMSSW_BASE etc. are set up:
echo $CMSSW_BASE   # -> /nix/store/...-cmssw-CMSSW_20_1_0_pre2

# the same for the 10_6 era:
nix build .#cmssw_10_6_30
nix develop .#cmssw_10_6_30
```

See [examples/MyAnalyzer](examples/MyAnalyzer) for building and running an
analyzer plugin against this CMSSW installation (self-contained, works with
both releases), [examples/MiniAODReader](examples/MiniAODReader) for
reading a real CMS Open Data miniAOD file with the 10_6_30 package, and
[examples/TrackerLocalReco](examples/TrackerLocalReco),
[examples/CaloLocalReco](examples/CaloLocalReco) and
[examples/MuonLocalReco](examples/MuonLocalReco) for running the tracker,
calorimeter and muon local reconstruction on toy digis with the XML-built
geometries and fake/hardcoded conditions.

## Layout

* `flake.nix` — inputs (nixpkgs, cmssw, alpaka, cms-md5 sources) and outputs
* `pkgs/cmssw.nix` — the main derivation: generates CMakeLists, builds,
  installs a release-area-like tree (`lib/`, `bin/`, `src/`, `python/`) and
  registers the EDM plugins
* `pkgs/cms-md5.nix` — the small md5 library CMS uses (`cms-externals/md5`)
* `gen/` — the BuildFile→CMake generator, the build configuration
  (`config.yml`), the top-level `CMakeLists.txt`, and the environment setup
  hook

## Notes

* `devShells.build` (and `devShells.build_10_6_30`) is for hacking on the
  CMSSW build itself (all deps, no cmssw): run the generator + cmake by hand
  against a local checkout.
* The `CMSSW_10_6_30` build is the python3 variant of that release (upstream
  shipped it as `cmsRunPython3`): the pybind11-based config parsing is simply
  built against python 3 instead of python 2, which no longer exists in
  nixpkgs.
* The Geometry/HLT/Sim/RecoLocal... subsystems of the old Arch config are not
  included, but extending `gen/config.yml` (and the dependency list in
  `pkgs/cmssw.nix` + `gen/CMakeLists.txt`) is all it should take.
