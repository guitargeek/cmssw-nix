# CMSSW on nix

A nix flake that packages most of CMSSW — 1,067 of the 1,371 packages of
the pre-release `CMSSW_20_1_0_pre4`, and 494 of the 1,255 of the Run-2
ultra-legacy release `CMSSW_10_6_30` — built with CMake instead of scram, so that people outside the CMS collaboration can run the CMS
**event-processing workflow end to end** on their own machine: event
generation with Pythia 8, detector simulation with Geant4 through the real
CMS geometry, digitisation into readout, the standard reconstruction chains
(tracking, vertexing, muons, calorimeters), and a flat NanoAOD ntuple out
the far end that plain ROOT reads. Conditions-database access is included
(sqlite payloads written and read back through `PoolDBESSource`, plus the
Frontier HTTP transport a real global tag uses).

Every stage is exercised by a runnable example under
[examples/](examples/) that doubles as a regression test with physics
assertions — not "did it compile", but "are the reconstructed momenta
within a percent of what the generator fired".

## Why two releases

* `CMSSW_20_1_0_pre4` (default): the current pre-release, proving the
  build tracks the modern codebase — C++20, DD4hep geometry, ONNX/XGBoost
  inference from nixpkgs.
* `CMSSW_10_6_30`: the release that actually read and wrote the archived
  Run-2 data (ultra-legacy), with an era-matched toolchain from a second
  nixpkgs pin (nixos-22.05: gcc 11 / C++17, ROOT 6.24, classic TBB,
  python 3.9). Built as the python3 variant of that release.

Both are built to the same scope and run the same example jobs from the
same configuration files, with the (documented) differences behind an
`_is_10_6` switch — see [docs/porting-10_6.md](docs/porting-10_6.md).

## What runs end to end

The flagship chain is [examples/MuonGunDigi](examples/MuonGunDigi), one
particle through every stage of the experiment's offline software:

| stage | validates |
|---|---|
| event generation ([NanoGen](examples/NanoGen)) | Pythia 8 Z → μμ → gen-level NanoAOD; Z peak recovered by plain ROOT |
| simulation ([MuonGunSim](examples/MuonGunSim)) | Geant4 transports muons through the full 2018 CMS geometry in the volume-based field; SimHits in pixel barrel, TIB, TOB, all four DT stations |
| digitisation | SimHits → pixel + strip + DT + calorimeter raw readout, with its simulated conditions read from a local sqlite tag |
| local reco | rec hits land 21 µm from the simulated crossings (strip pitch /√12, i.e. at resolution) |
| tracking + vertexing | 100% of muons reconstructed, momentum to **0.7%**, charge right every time; primary vertex within 9 µm of the gun |
| muon system | the same muons measured a second time in the yoke alone (independent probe of the field where the tracker does not sample it) |
| calorimeters | the textbook MIP: E/p = 0.9%, HCAL response at the barrel sampling factor |
| raw data (20_1) | HCAL digis packed into FED buffers, written to an HLT streamer file, unpacked: all 57600 channels back sample for sample |
| tracking validation (20_1) | the standard release validation (`MultiTrackValidator`, the harvesting, a DQM file): 19 of 20 muons associated to a track by their hits, no fakes, no duplicates |
| tracker DQM (20_1) | the detector groups' monitoring of the same events (pixel, strip, tracking): strip cluster charge in the ratio of the sensor thicknesses, outer to inner barrel |
| L1 trigger (20_1) | the Run 3 barrel muon trigger emulated on the DT digis (trigger primitives → TwinMux → Kalman BMTF → uGMT): 19 of 20 muons trigger, all with the right charge |
| HLT (20_1) | the menu's `HLT_Mu20` through its standalone-muon step, on the L1 Global Trigger emulated with a real L1 menu: 13 of 15 muons above 25 GeV kept |
| fast simulation (20_1) | the same muons through FastSim instead of Geant4, digitisation and clustering, into the same tracking: 180 of 200 tracked at 0.65% momentum resolution (the full chain: 19 of 20 at 0.44%), in under a millisecond an event |
| combination → ntuple | tracker + standalone fits merged into `reco::Muon`, written to a NanoAOD file, read back by plain ROOT and matched to the generated muons |

Standing alone, [examples/TrackerLocalReco](examples/TrackerLocalReco),
[CaloLocalReco](examples/CaloLocalReco), [MuonLocalReco](examples/MuonLocalReco),
[TrackingChain](examples/TrackingChain) and
[MuonChain](examples/MuonChain) exercise the same reconstruction on toy
data; [MiniAODReader](examples/MiniAODReader) reads a real UL2016
MINIAODSIM file from CMS Open Data with zero dictionary warnings;
[MagneticFieldMap](examples/MagneticFieldMap) validates the interpolated
field profile; [ConditionsSqlite](examples/ConditionsSqlite) writes and
reads a conditions payload; [ConditionsFrontier](examples/ConditionsFrontier)
drives the Frontier transport against a stub servlet.

On 20_1, [examples/CmsDriverChain](examples/CmsDriverChain) runs what
`cmsDriver.py` writes, unmodified: a 2024 MC production in four steps,
GEN-SIM, DIGI-L1-DIGI2RAW-HLT, RECO-PAT and NANO, with the whole standard
sequences of the release (the 2024 HLT menu, the TensorFlow and ONNX
networks of the reconstruction, the alpaka modules on the CPU, NanoAOD).
The flake check constructs every module of the four jobs offline; run with
conditions from the global tag over Frontier, 10 muon-gun events come out
of the NanoAOD with every generated muon reconstructed.

## What is packaged

* **Framework and I/O** — full `FWCore`, plugin manager, python
  configuration, `PoolSource`/`PoolOutputModule`, and scram's "cfipython"
  fragments regenerated at install time, so stock CMSSW configs load
  unchanged.
* **Data formats** — everything a Run-2 (mini)AOD event record contains:
  reco physics objects, `pat::Candidates`, generator/pileup truth,
  forward-proton and L1 stage-2 formats.
* **Conditions** — CORAL (CMS fork) with SQLite backend, the full
  `CondCore` write/read path, serialization code generated by CMSSW's own
  libclang generator, and the Frontier client with its CORAL backend.
* **Geometry** — the XML-built tracker/calorimeter/muon geometries and the
  volume-based magnetic field interpolated from the real grid tables.
* **Reconstruction** — local reco for all subdetectors, the complete
  tracking/vertexing machinery, standalone/global muons, e/gamma,
  particle flow, jets/MET with corrections, b/τ-tagging (lwtnn
  DeepFlavour included).
* **Analysis formats** — the PAT layer (`PhysicsTools/PatAlgos`) and
  NanoAOD on 20_1, with the DQM core, the L1 menu utilities and the HLT
  configuration readers they depend on (`DQMServices/Core`,
  `L1Trigger/L1TGlobal`, `HLTrigger/HLTcore`); NanoAOD on 10_6.
* **Raw data** — on 20_1, the packers and unpackers of every subdetector
  (`EventFilter/*RawToDigi`, `*DigiToRaw`) and the streamer file format
  (`IOPool/Streamer`, the DAQ sources in `EventFilter/Utilities`), so the
  standard `RawToDigi` and `DigiToRaw` sequences load.
* **L1 trigger emulators** — on 20_1, `L1Trigger` and `L1TriggerConfig`:
  trigger primitives, the muon track finders, the calorimeter layers, the
  global triggers, Stage-2 and legacy, with the lookup tables of
  `L1Trigger-L1TMuon` and the 2022 L1 menu from `L1Trigger-L1TGlobal`.
  The trained models the Run 3 emulation loads at run time are packaged too
  (CICADA, AXOL1TL, the EMTF network). Not the Phase-2 calorimeter and
  particle-flow trigger, which need the conifer BDT library, and the legacy
  CSC track finder only as configuration (its external is not packaged).
* **Validation and offline DQM** — on 20_1, `Validation` and `DQMOffline`,
  with the truth they compare against (TrackingParticles from the mixing
  module, the track associators) and the rest of the DQM framework
  (`DQMServices/Components`, the DQM file formats and sources). Not what
  validates the Phase-2 L1 trigger, which needs TensorFlow or conifer:
  `DQMOffline/L1Trigger`, `Validation/SiTrackerPhase2V`, and the plugins
  of `Validation/HGCalValidation`.
* **DQM** — on 20_1, the subsystem monitors and clients of `DQM/` for
  every detector and the L1 trigger. Not the two that write to the online
  databases (`EcalMonitorDbModule`, `SiStripCommissioningDbClients`: Oracle
  and the tracker's online configuration database), the DIP publisher of
  the beam spot, and the monitors of the legacy CSC track finder.
* **HLT** — on 20_1, `HLTrigger` (the filters and producers, the menus,
  the `FastTimerService`) and the offline monitoring of the paths in
  `HLTriggerOffline`. The HLT menus run as far as the modules this build
  has: the alpaka modules on the CPU backend (no GPU backends), and not
  the L3 muons' DNN seeder, which needs conifer.
* **Fast simulation** — on 20_1, `FastSimulation` and `FastSimDataFormats`,
  with the pixel resolution histograms from cms-data
  (`FastSimulation-TrackingRecHitProducer`) and two of its pixel templates
  (`CalibTracker-SiPixelESProducers`). Not the CTPPS proton tracking's
  plugin (Hector is not packaged), and not the nuclear interactions of
  hadrons, whose library of Geant4 events is not distributed with the
  release.
* **Simulation and generation** — Geant4 with `SimG4Core`/`SimG4CMS`, and
  Pythia 8 with `GeneratorInterface`: the 8.240 CMS fork for 10_6, and
  8.317 for 20_1, the version CMS builds it with; on 20_1 also Tauola++
  (with TauSpinner) and Rivet. Not the EvtGen and Photos decay plugins, or
  the fortran-based Madgraph and Alpgen jet matching (the FastJet-based
  MLM matching is there).

Machine learning: on 20_1 the TensorFlow C++ API (from nixpkgs' binary
wheel, [pkgs/tensorflow-cc.nix](pkgs/tensorflow-cc.nix)), ONNX Runtime and
XGBoost, so the reconstruction's networks (the tracking DNNs, mkFit,
DeepCore, DeepTau, DeepMET, DeepSC) are built. One protobuf runs in the
process, TensorFlow's 6.31.1, which ONNX Runtime and the release are built
against too ([flake.nix](flake.nix)). Deliberately out: the Triton
inference client (SONIC), PyTorch, and the conifer BDT library, whose
consumers are pruned at prepare time and fail loudly if configured. Where configuration
code imports the cfi of such a module anyway (to swap it in under a process
modifier), the install phase writes a placeholder for it
([gen/placeholder_cfis.py](gen/placeholder_cfis.py)), so the configuration
loads and only a job that runs the module fails. Also out: online and
HcalTrigger selection packages that only exist upstream.

External software: almost everything from nixpkgs (ROOT, boost, Geant4,
ONNXRuntime, XGBoost, fastjet, clhep, …). Packaged here in
[pkgs/](pkgs/) are only the CMS-specific externals: CORAL, the Fermilab
frontier client, cms-md5, HepPDT, lwtnn, Pythia 8 (the CMS fork, for 10_6), the Xilinx
HLS headers, the hls4ml emulator interface and the L1 trigger's hls4ml
models, DD4hep, classlib, the L1 menu library utm, vdt, Tauola++, the
TensorFlow C++ API out of its wheel, and a standalone Minuit2 for the
10_6-era ROOT. The cms-data the standard Run 3 sequences read (some 2 GB)
is not part of the default release: `cmssw_20_1-with-reco-data` is the same
build with it merged in ([pkgs/cmssw-release.nix](pkgs/cmssw-release.nix)).

It is the successor of an earlier Arch Linux PKGBUILD experiment: the
`BuildFile.xml` → `CMakeLists.txt` conversion script from there lives on
in [gen/cmssw_cmake.py](gen/cmssw_cmake.py), now driven by a nix
derivation.

## Usage

```bash
nix build .#cmssw_20_1     # the release (also the default package); hours
nix develop                # shell with cmsRun, the release, cmake and ROOT

# inside the shell, CMSSW_BASE etc. are set up:
echo $CMSSW_BASE   # -> /nix/store/...-cmssw-CMSSW_20_1_0_pre4

# the same for the 10_6 era:
nix build .#cmssw_10_6
nix develop .#cmssw_10_6

# 20_1 with the cms-data the standard Run 3 sequences read (some 2 GB),
# for jobs that cmsDriver.py writes (see examples/CmsDriverChain)
nix develop .#with-reco-data
```

See [examples/MyAnalyzer](examples/MyAnalyzer) for how to build and run an
analyzer plugin against this CMSSW installation (self-contained, works
with both releases).

## Platforms

Both releases build and pass the example suite on `aarch64-darwin` (Apple
silicon) and `x86_64-linux`; the 20_1 package on macOS needs macOS 26 or
later, for the floating-point `std::from_chars` of the system C++ library.
On Linux, in the build sandbox, a 12-core machine with 29 GB of memory
compiles 20_1 in a little over four hours. What the macOS port changed, and
the clang and libc++ issues it found in CMSSW, are in
[docs/macos.md](docs/macos.md).

## Testing

```bash
nix flake check          # builds and runs every example, both releases
```

(If the releases themselves are not built yet this builds them first, which
is hours — see [docs/development.md](docs/development.md).)

Each example directory is a check of its own, so they build in parallel
and a failure names the example that broke. Per release, two more:
`libsweep-<era>` `dlopen`s every library (a library that links cleanly can
still be unusable at run time: a pruned source file, a missing external, an
unallocated Fortran common block), and `prepare-<era>` runs only the source
edits and the CMake generator, in minutes, which is what breaks first when
the sources move.

The jobs the checks run are listed in
[examples/jobs.json](examples/jobs.json), which
[examples/run_all.sh](examples/run_all.sh) reads too, so the hermetic and
the interactive runner cannot drift apart:

```bash
nix develop .#cmssw_10_6 -c ./examples/run_all.sh 10_6
```

`run_all.sh` builds in the working tree, so an edit to an example is one
`cmake --build` away from being tested; `nix flake check` builds from the
store and is what to trust.

## Layout

* `flake.nix` — the inputs, the externals and the releases; the outputs
  (`cmssw_<era>`, `cmssw-build_<era>`, the dev shells, the checks) are
  generated from its `releases` table
* `pkgs/cmssw.nix` — the build of a release: prepares the sources,
  generates the CMakeLists, builds, installs a release-area-like tree
  (`lib/`, `bin/`, `src/`, `python/`) and registers the EDM plugins. Its
  optional externals are one table, `optionalExternals`.
* `pkgs/cmssw-release.nix` — the release users get: the build with the
  cms-data it reads merged into its release area
  ([gen/release-with-data.sh](gen/release-with-data.sh)), links only, so a
  data change does not rebuild the release
* `pkgs/cms-data.nix`, `pkgs/cms-data.json` — cms-data repositories; the
  JSON pins those of the standard sequences, and
  [scripts/update-cms-data.py](scripts/update-cms-data.py) moves them to
  another release
* `pkgs/` — the CMS-specific externals
* `gen/prepare/` — the edits to the CMSSW sources, by kind: what this build
  leaves out (`scope.py`), newer externals and compilers (`toolchain.py`),
  clang/libc++/macOS (`portability.py`) and bugs in CMSSW (`fixes.py`). An
  edit that no longer applies is an error.
* `gen/cmssw_cmake.py`, `gen/CMakeLists.txt` — the BuildFile → CMake
  generator and the top-level CMakeLists that defines the scram tools; a
  tool a BuildFile uses but the CMakeLists does not define stops the
  configuration
* `gen/config.yml`, `gen/config-10_6.yml` — the packages each release builds
* `nix/` — the 22.05 darwin overlay, the dev shell and check builders
* `examples/` — the example jobs (`jobs.json`) and what they share
  (`cmake/`, `common/`, `data/`)
* `scripts/` — `build.sh` (build and pin the releases), `push-cache.sh`,
  `worktree.sh` (incremental builds while working on the build)
* `docs/` — [macOS](docs/macos.md), [working on the build](docs/development.md),
  [10_6 vs 20_1](docs/porting-10_6.md)
