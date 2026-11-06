# MuonGunSim

Geant4 detector simulation: fire muons into the real CMS geometry and read
back the SimHits they leave.

This is the first example here where a particle is actually transported.
Everything before it either read hits out of a file or built toy digis by
hand. Here `OscarMTProducer` constructs the whole CMS detector from the DDD
XML description, hands it to Geant4, and steps muons through it in the
volume-based magnetic field — the hits come out of the transport, not out of a
producer that was told what to write.

Needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`).

## What had to be packaged

* `pkgs/geant4.nix` — Geant4 10.4.p03 from `cms-externals/geant4`. The version
  is fixed, not a floor: nothing in SimG4Core or SimG4CMS is guarded by
  `G4VERSION_NUMBER`, so the code compiles against exactly one Geant4 API.
  nixpkgs ships the 11 series, which moved too much of it.
* `pkgs/geant4-data.nix` — the ten physics datasets (cross sections, atomic
  transition and nuclear level data), ~620 MB. Geant4's CMake would download
  these mid-build, which a nix build cannot do, so they are fixed-output
  derivations pinned by hash and exported through the ten `G4*DATA`
  environment variables.
* 19 new CMSSW packages in `gen/config-10_6.yml` — SimG4Core (the run
  managers, the DDD→G4 geometry translation, the physics lists, the field
  integration) and SimG4CMS (the sensitive detectors that turn a Geant4 step
  into a `PSimHit`), plus the particle guns and the geometry XML that only a
  simulation needs.

Four details that are easy to get wrong and do not fail loudly:

* **CLHEP has to be shared.** Geant4 vendors its own copy, but CMSSW links the
  system CLHEP and passes CLHEP types across the boundary. Two copies in one
  process means two sets of static random engines and two definitions of
  `Hep3Vector`. `GEANT4_USE_SYSTEM_CLHEP=ON` keeps it to one.
* **`Geant4_DEFINITIONS` has to be propagated.** `find_package(Geant4)`
  exports `-DG4MULTITHREADED`, `-DG4_STORE_TRAJECTORY` and `-DG4VERBOSE`, and
  the first two change the layout of `G4Event` and `G4TrackingManager`. Code
  compiled without them against a toolkit built with them links cleanly and
  then reads the wrong offsets. `gen/CMakeLists.txt` was dropping them.
* **...and `Geant4_DEFINITIONS` is not all of the definitions.**
  `-DG4USE_STD11` is exported in `Geant4_CXX_FLAGS` instead, among the warning
  options, and `tls.hh` keys `G4ThreadLocal` on it: with the macro it is
  `thread_local`, without it `__thread`. 238 installed headers declare
  variables with that macro, so omitting it makes every CMSSW translation unit
  disagree with the toolkit about how they are declared. It becomes a hard
  error only where the type has a destructor, which `__thread` forbids —
  `SimG4Core/CustomPhysics` has a `G4ThreadLocal std::unique_ptr` and is the
  one place in the release that says so out loud. The build now takes the `-D`
  options out of `Geant4_CXX_FLAGS` as well.
* **The plugin cache has to be built with the TLS surplus.**
  `edmPluginRefresh` dlopens every plugin to index it, so inside the nix build
  it needs the same `GLIBC_TUNABLES` surplus `gen/setup-hook.sh` gives
  consumers — the hook does not apply to our own build. Without it every
  Geant4-linked plugin fails with `cannot allocate memory in static TLS
  block`, and `edmPluginRefresh` reports that and exits 0. The libraries are
  then correct and complete and `cmsRun` still says `Unable to find plugin
  'OscarMTProducer'`. `pkgs/cmssw.nix` sets the tunable and now fails the
  build if any plugin did not load.
## What is tested

`SimHitCounter` asserts on hits that a muon gun cannot avoid producing. The
gun fires into `|eta| < 0.8`, so every muon crosses the pixel barrel, the TIB,
the TOB and then all four DT stations; those four collections have to be
non-empty. It also checks the total energy deposit is in the range a
minimum-ionising particle gives — of order 100 keV per sensor, so neither zero
nor GeV-scale. A run that built the wrong geometry, lost the field or failed
to attach its sensitive detectors misses at least one of these.

`muon_gun_sim_cfg_check.py` then reopens the written file with FWLite, the way
an analysis would, and confirms the collections survived being streamed to
ROOT and read back — which is what DIGI and RECO will do to them next.

## What is not tested: the forward shower libraries

`g4SimHits_cfi` names two data files that are not in the release tarball:

```
SimG4CMS/Calo/data/HFShowerLibrary_oldpmt_noatt_eta4_16en_v3.root
SimG4CMS/Forward/data/CastorShowerLibrary_CMSSW500_Standard.root
```

These are pre-generated shower libraries for HF and Castor, distributed
separately. The `download.url` stubs in the release point at
`cmsdoc.cern.ch`, which now sits behind CERN SSO, and the
`cms-data/SimG4CMS-Calo` repository is empty — there is no way to fetch them
here.

Working around it is not optional: `edm::FileInPath` resolves when the python
configuration is translated into the C++ `ParameterSet`, before any module is
constructed, so an unresolvable path aborts the job at startup even though
nothing would ever have read the file. The config points both at a file that
does ship and switches the libraries off, so HF and Castor fall back to
parameterised showers.

That costs this example nothing — a muon in `|eta| < 0.8` never reaches HF
(`|eta| > 3`) or Castor (`|eta| > 5`) — but it does mean **forward
calorimeter simulation is not exercised anywhere in this flake**, and any
later stage that needs realistic HF showers will need those files from a
machine with CERN credentials.

Switching the libraries off is more delicate than it looks, in two ways.

**The HF switch is on `HCalSD`, not on `HFShower`.** `HCalSD`'s constructor
reads `UseShowerLibrary` from its own PSet and only then decides whether to
construct an `HFShowerLibrary`; the `HFShower` and `HFShowerLibrary` PSets
configure those objects once they exist and cannot stop one being built.
Setting the flag on the wrong PSet leaves the library constructed, and the job
dies on the first event with `HFShowerLibrary Events tree absent` — it opened
the `.dat` file the config pointed it at and looked for a ROOT tree.

**`CastorSD` deletes a pointer it never initialised.** This is an upstream bug
that only a job with the library switched off can reach. `CastorShowerLibrary*
showerLibrary` is a raw member; the constructor assigns it only inside
`if (useShowerLibrary)`, the initialiser list covers the other six pointer
members and omits this one, and `~CastorSD` runs `delete showerLibrary`
unconditionally. With the library on the pointer is always valid, which is why
production never sees it. With it off, `cmsRun` segfaults on the way out —
after every event has been simulated and written, so the output file is
complete and only the exit code is wrong. `gen/prepare` adds
`showerLibrary(nullptr)` to the initialiser list.

## Two things the standard sequences would have done for us

This package subset has `SimG4Core` and `SimG4CMS` but not
`Configuration/StandardSequences`, so a couple of wiring steps that a
`cmsDriver` config inherits have to be written out here.

* **The particle data table.** `FlatRandomPtGunProducer` looks the muon's mass
  and charge up in the PDT at begin-run, and Geant4 builds its particle list
  from the same table. Without `SimGeneral.HepPDTESSource.pythiapdt_cfi` the
  job dies at global begin run with `No "PDTRecord" record found in the
  EventSetup`, before the gun fires once.
* **The name of the vertex-smearing module.** `g4SimHits` reads
  `HepMCProductLabel = cms.InputTag("generatorSmeared")`, but the
  `VtxSmeared*_cfi` files all name their module `VtxSmeared`. Nothing in this
  subset bridges the two, so the config renames it.

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30`:

```bash
cmake -B build -S . -G Ninja
cmake --build build

export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

cmsRun python/muon_gun_sim_cfg.py
python3 python/muon_gun_sim_cfg_check.py
```
