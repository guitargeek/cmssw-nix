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

On top of the local reconstruction, the build now carries the **complete
high-level reconstruction chain**: the full `TrackingTools` +
`RecoTracker` + `RecoPixelVertexing` + `RecoVertex` tracking and vertexing
machinery, standalone/global/tracker muons (`RecoMuon`), e/gamma
clustering and identification (`RecoEcal`, `RecoEgamma`), particle flow
(`RecoParticleFlow`), jets and MET with their corrections (`RecoJets`,
`RecoMET`, `JetMETCorrections` with fastjet + fastjet-contrib), b- and
tau-tagging (`RecoBTag` incl. the lwtnn-based DeepFlavour,
`RecoTauTag`), and the supporting `PhysicsTools`/`CommonTools`/
`SimDataFormats` layers — about 430 packages in total. New externals:
fastjet(+contrib) and openblas from nixpkgs, HepPDT and lwtnn packaged
here ([pkgs/heppdt.nix](pkgs/heppdt.nix), [pkgs/lwtnn.nix](pkgs/lwtnn.nix)).
The chain is validated end-to-end without external data: toy digis placed
along true helices through the XML-built tracker reconstruct — through
the standard clusterizers, pixel-triplet seeding, helix fit and
primary-vertex fit, and onward through the full combinatorial Kalman
filter (`CkfTrackCandidateMaker` + `CTFFinalFitWithMaterial`) — into the
injected tracks (momenta reproduced to a few permil with 16–21 hits) and
a primary vertex at the origin (see
[examples/TrackingChain](examples/TrackingChain)).

The **real (volume-based) magnetic field** is available as well, not just the
uniform 3.8 T approximation: the field volumes are parsed from their own XML
description and the field inside them is interpolated from the grid tables of
the `cms-data` external `MagneticField-Interpolation`, which the 10_6 build
installs under `MagneticField/Interpolation/data`. The profile it gives —
3.81 T on the beam line, through zero in the gap between cryostat and return
yoke, back to −1.29 T inside the barrel yoke iron — is validated in
[examples/MagneticFieldMap](examples/MagneticFieldMap). (The data external
carries all six table sets, about 480 MB, of which only the 3.8 T set is used
by default.)

**Event generation with Pythia 8** is the newest stage — the first step of
the road towards full event simulation up to nanoAOD. Pythia 8.240 (the
version of the 10_6 release era, from CMS's fork) is packaged in
[pkgs/pythia8.nix](pkgs/pythia8.nix), with LHAPDF and libsigc++ from
nixpkgs; `GeneratorInterface` is built with the DIRE/VINCIA/EvtGen hooks
replaced by stubs that fail clearly at runtime if configured, and with the
fastjet-based MLM matching kept (the fortran-based Madgraph/Alpgen matchers
are pruned). On top of it sit the **nanoAOD flat-table producers**
(`PhysicsTools/NanoAOD`), so the build can go from a physics process to an
analysis-ready file: [examples/NanoGen](examples/NanoGen) generates
Z → μμ, runs the standard GenParticle pruning, AK4 gen-jet clustering and
the GenPart/GenJet/weights tables, and writes a real NanoAOD file — which
the example then re-opens with plain ROOT (no CMSSW) and re-finds the Z
peak in.

With the real field in place, **standalone muon reconstruction** works: a
50 GeV muon stepped out of the origin through that field leaves DT digis in
four barrel chambers, and the standard chain (rec hits → 4D segments →
`ancientMuonSeed` → `StandAloneMuonProducer`) fits them back into a
`reco::Track` carrying all 32 hits with the right charge and direction — see
[examples/MuonChain](examples/MuonChain). This is the step a uniform field
cannot do, since the fit lives entirely in the region where the flux has
returned through the iron.

The self-contained examples double as a regression suite;
[examples/run_all.sh](examples/run_all.sh) builds and runs all of them for
either release:

```bash
nix develop .#cmssw_10_6_30 --command ./examples/run_all.sh 10_6
nix develop --command ./examples/run_all.sh 20_1
```

The install also generates scram's "cfipython" configuration fragments:
`edmWriteConfigs` is run over every built library at install time (via a
library→package manifest emitted by the generator) and everything it writes
is merged into the package python directories, so the standard configuration
files that import them work unchanged. Note that this is more than the
`*_cfi.py` files: a modern module also gets a `<ModuleType>.py` builder
alongside its `<label>_cfi.py`, and the cfi imports it — keeping only the
`_cfi.py` files leaves those unimportable, which surfaces much later as a
`ModuleNotFoundError` inside a `process.load()`.

Still out of scope: the DNN-based producers that need the TensorFlow C++
or ONNXRuntime externals (DeepMET, DeepTau, DeepJet — pruned at prepare
time), the HLT/trigger tooling (would need the `utm` external), and the
generator packages.

### The same scope for `CMSSW_20_1_0_pre2`

The modern release is built to the same scope (472 packages): the local
and high-level reconstruction chains, the conditions and geometry
machinery, and the supporting data formats. Because 20_1 moved its
geometry onto **DD4hep** (the builders link it from their main libraries,
where the 10_6 era still had a prunable DDD code path), it is packaged
here in [pkgs/dd4hep.nix](pkgs/dd4hep.nix); the L1 trigger data formats
additionally need the Xilinx arbitrary-precision headers
([pkgs/hls.nix](pkgs/hls.nix)), and Geant4, HDF5, HepMC 2 *and* 3 come
from nixpkgs. The e/gamma clustering and identification chain, the particle-flow
blocks and tau ID are included as well: **ONNXRuntime** and **XGBoost**
come from nixpkgs and carry the electron/photon identification MVAs, the
PF DNN and the b-tagging DNNs. Two inference backends remain out of
reach — the TensorFlow C++ API (nixpkgs' `libtensorflow` is broken and
ships only the C API, and the wheel that carries `libtensorflow_cc` is
not fetchable in a sandboxed build) and the Triton client for SONIC
remote inference. Their handful of consumers are pruned at prepare time
the same way the 10_6 build prunes DeepTau: the DeepSC superclustering,
the DeepTau discriminators, the DNN muon seeder and the SONIC producers.
Where a pruned code path is user-selectable, it now raises a clear
runtime error (`SCProducerCache` refuses `ClusteringType = "DeepSC"`)
rather than silently behaving differently.
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
geometries and fake/hardcoded conditions, and
[examples/MagneticFieldMap](examples/MagneticFieldMap) for the volume-based
magnetic field.

## Layout

* `flake.nix` — inputs (nixpkgs, cmssw, alpaka, cms-md5 sources) and outputs
* `pkgs/cmssw.nix` — the main derivation: generates CMakeLists, builds,
  installs a release-area-like tree (`lib/`, `bin/`, `src/`, `python/`) and
  registers the EDM plugins
* `pkgs/cms-md5.nix` — the small md5 library CMS uses (`cms-externals/md5`)
* `gen/` — the BuildFile→CMake generator, the build configuration
  (`config.yml`), the top-level `CMakeLists.txt`, and the environment setup
  hook
* `gen/plan_packages.py` — works out *which* packages a release can build:
  it walks the `BuildFile.xml` dependency graph to a fixpoint (a package is
  buildable when none of its externals are missing and all its dependencies
  are buildable, modelling the edits `prepare_sources.py` makes) and writes
  the configuration. This is how `gen/config.yml` was produced from the
  10_6 configuration as the target scope:

  ```bash
  python3 gen/plan_packages.py --src <cmssw source> --base gen/config.yml \
      --wanted gen/config-10_6.yml --output gen/config.yml
  ```

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
