# MuonGunDigi

Digitisation: turn the energy Geant4 deposited in the silicon into the ADC
counts the strip tracker actually reads out.

[examples/MuonGunSim](../MuonGunSim) stops at `PSimHit`s — a position, a
direction and an energy loss per sensitive volume. That is not what a detector
produces. A strip module produces amplitudes on numbered channels, after
charge drift and Lorentz deflection, capacitive coupling between neighbouring
strips, the APV shaping pulse, amplifier noise, and zero suppression. Turning
one into the other is the DIGI step, and it is what makes simulated data
readable by the same reconstruction that runs on detector data — the chain
[examples/TrackerLocalReco](../TrackerLocalReco) demonstrates on digis it
builds by hand.

Needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`).

## The digitisers live inside the mixing module

They are not ordinary producers. `SimGeneral/MixingModule` owns them and calls
them, because in a real job the same code has to see the signal event and the
pileup events through one interface. There is no pileup here — `mix` runs with
a single bunch crossing and no secondary input — but the step still goes
through it, and the digis come out under `mix`'s product names, given their
familiar labels by the same `EDAlias` the standard configuration uses.

That alias keeps the *instance* names, which matters when reading them back:

```
edm::DetSetVector<SiStripDigi>      "simSiStripDigis"  "ZeroSuppressed"
edm::DetSetVector<SiStripRawDigi>   "simSiStripDigis"  "VirginRaw"
edm::DetSetVector<StripDigiSimLink> "simSiStripDigis"  ""
```

`ZeroSuppressed` is the one the detector reads out; the raw flavours are what
the readout would have seen before suppression.

## What is tested

`DigiCounter` asserts something a non-empty check would not: **the modules
carrying digis are the modules the muon crossed**. It reads both the PSimHits
and the digis and requires that essentially every hit module produced a digi —
a minimum-ionising particle deposits far more than any zero-suppression
threshold, so a module that was hit and stayed silent means the digitiser and
the geometry disagree about which module is which.

It covers both detectors: 43/43 hit pixel modules and 153/153 hit strip
modules digitise. The contrast between them is itself informative — about
90 pixel digis an event against 87 000 strip digis, because the strip
digitiser puts noise on every channel in the tracker while pixels have
negligible noise occupancy.

The converse is deliberately not asserted. The digitiser adds noise to every
channel in the tracker, so most modules with digis were never touched by the
muon: a typical run here is ~87 000 digis across ~6 500 modules per event,
against 153 modules that actually contain a hit. That is correct behaviour,
not something to assert against.

`muon_gun_digi_cfg_check.py` then reopens the file with FWLite and confirms
the digis stream to ROOT and come back as themselves, which is what local reco
and RAW packing rely on.

## Two jobs, because the simulated conditions need a database

`python/write_sim_conditions_cfg.py` runs first and writes a small sqlite file;
`python/muon_gun_digi_cfg.py` reads it. This is not ceremony — the strip
digitiser needs two payloads that no fake ES source in the release can
provide:

* **`SiStripLorentzAngleSimRcd`** — the *simulated* Lorentz angle, a different
  record from the `SiStripLorentzAngleRcd` reconstruction uses. Every fake
  source serves the reconstruction record only
  (`SiStripLorentzAngleFakeESSource.cc:112`), and nothing in the release
  produces the Sim record at all.
* **`SiStripApvGainSimRcd`** — likewise. And here the record structure bites:
  `SiStripGainSimRcd` is a *dependent* record declared over
  `SiStripApvGainSimRcd`, so pointing `SiStripGainSimESProducer` at the
  reconstruction gain is not enough. The framework still wants an IOV for
  `SiStripApvGainSimRcd` itself and fails with *"no valid IOV for the
  synchronization value"* rather than a missing-record error.

In production both come from the global tag, which is why neither is ever
noticed. The writer takes the ideal payload out of the fake source and files
it under the record name the digitiser will ask for, using CMS's own
`DummyCondDBWriter` — the module copies an EventSetup object into the
conditions output service, and the output service decides which record it is
stored as. [examples/ConditionsSqlite](../ConditionsSqlite) is the same
machinery on its own.

Reading those payloads back also needs `CondCore/SiStripPlugins`, whose
`plugins/plugin.cc` holds the `REGISTER_PLUGIN` list that gives
`PoolDBESSource` its record proxies. Without it the job fails with *"Unable to
find plugin 'SiStripLorentzAngleSimRcd@NewProxy'"*. Only that one library is
built: `gen/prepare_sources.py` drops the eleven payload inspectors beside it,
which need `boost_python` and are a web display tool.

## Closing the loop: local reconstruction

`python/muon_gun_reco_cfg.py` reads the digi file back and runs the strip
local reconstruction on it — the standard three-threshold clusteriser and
`SiStripRecHitConverter` — then asks the question that gives the whole
chain a point: **are the rec hits where the muon actually went?**

```
reconstructed 169/169 SimHits (100%), median |dx| = 21.1 um, RMS = 55.2 um
```

21 µm is the answer it should give. The TIB strip pitch is 80 µm, and a
one- or two-strip cluster localises to about pitch/√12 ≈ 23 µm, so the
reconstructed position sits on the digitisation resolution. That single
number exercises the geometry, the drift and Lorentz deflection applied at
digitisation, the charge sharing between neighbouring strips, the cluster
charge weighting and the CPE — all of which have to agree with each other
to land there. A digitiser that wrote plausible ADC counts into the right
modules but the wrong strips would pass every assertion in the DIGI job
above and fail this one by hundreds of microns.

Two things have to match the digitisation job for the comparison to mean
anything, and both are set explicitly in the config: the **geometry**
(DetIds and module-local frames are only meaningful against the geometry
they were produced in) and the **magnetic field** (the CPE corrects the
cluster position for Lorentz drift, so it has to see the field that drift
was generated with).

The matching runs from SimHit to nearest rec hit, never the reverse. The
digitiser puts noise on every channel in the tracker, so there are rec hits
in thousands of modules no particle ever entered; they say nothing about
whether reconstruction works and would only add a tail.

Both single-sided collections are read. TIB layers 1–2 and TOB layers 1–2
are double-sided, and the stereo sensor of a double-sided module is a
separate `DetId` whose rec hits land in `stereoRecHit`; reading only
`rphiRecHit` leaves every stereo SimHit permanently unmatched and costs a
third of the efficiency for no physical reason.

This is also what [examples/TrackerLocalReco](../TrackerLocalReco) does,
except that it feeds the clusteriser from a hand-written
`ToyTrackerDigiProducer`. The one line that differs is its
`DigiProducersList`. Running the same reconstruction on digis that came
out of a real simulation is what retires the "toy" in that example.

## The pixel Lorentz angle, and a conditions bug the residuals caught

The residual test earned its place here. With the pixel digitiser turned
on, the first measurement came out:

```
pixel: median x = 51 um, y = 23 um
```

y was right for a 150 um pitch. x was not: 100 um pixels with charge
sharing should do better than 80 um strips, and this was three times
worse. Nothing failed — every job exited 0, the digis were in the right
modules, and the DIGI assertions all passed.

What acts on pixel local x specifically is the Lorentz drift: the field
is along z, so the carriers drift entirely in r-phi. Setting the
digitiser's Lorentz angle to zero collapsed the residual to 22 um, which
showed the drift was being applied at digitisation and never undone in
reconstruction. Swapping the volume-based field for a uniform one changed
nothing at all — bit-identical output — so the correction was not merely
wrong, it was absent.

The cause is that `SiPixelFakeLorentzAngleESSource` builds its payload by
looping over the DetIds in
`CalibTracker/SiPixelESProducers/data/PixelSkimmedGeometry.txt`, and that
file describes the **phase-0** pixel detector — 1440 modules. The 2018
geometry simulated here is phase-1: 1856 modules, different DetIds. Not
one module in the job appears in the payload,
`SiPixelLorentzAngle::getLorentzAngle` returns zero for every one of them,
and the CPE dutifully corrects by nothing.

`plugins/PixelLorentzAngleWriter.cc` fixes it by building the payload from
the `TrackerGeometry` the job is actually running — the same flat 0.106,
over the right DetIds. That takes the pixel residual from 51 um to 9 um,
and the assertion is set at 30 um so the regression cannot come back
unnoticed.

The same phase-0 file backs the fake pixel gain and quality sources. Those
do not matter here — the clusteriser runs with `MissCalibrate=False` and
nothing is marked bad — but the pattern is worth remembering: **a fake
pixel ES source in this release is describing a detector that was replaced
in 2017.**

## The pixel FED cabling map, which is empty on purpose

`SiPixelDigitizerAlgorithm` fetches `SiPixelFedCablingMapRcd`
unconditionally at line 128 — there is no switch beside the
`use_deadmodule_DB_` and `use_LorentzAngle_DB_` guards on the lines above
it — so the record has to exist or the job dies on the first event. The
two places that dereference the handle are both behind conditions that are
off here: one needs `KillBadFEDChannels`, the other fires only for ROCs a
quality payload marks bad.

A real map cannot be built in this release anyway.
`SiPixelFedCablingMapBuilder` needs an ASCII module-to-link description,
and the only ones shipped are phase-0, in
`CalibTracker/SiPixelConnectivity/test`, which this build does not install.
The phase-1 file the 2018 detector would need,
`pixelToLNK.ascii_phase1_v1`, is named by the release's own writer
configuration and is not shipped with it — the same phase-0/phase-1 gap as
the Lorentz angle above, in a place where it cannot be closed from the
geometry.

So `plugins/PixelCablingMapWriter.cc` writes an explicitly empty map. That
is the honest option: it cannot be mistaken for a real cabling
description, and if either guarded branch were ever reached,
`pathToDetUnit` returns an empty vector and the loops do nothing rather
than reading a map for the wrong detector.

## Two upstream bugs found on the way

Neither is reachable from a production job, because both live on the
no-database path this flake is necessarily on.

* **`SiStripPedestalsFakeESSource_cfi` cannot configure its own ES source.**
  The cfi sets `PedestalsValue`; the C++ reads `PedestalValue`
  (`SiStripPedestalsFakeESSource.cc:48`). `process.load` of the shipped cfi
  fails outright. The config here writes the ESSource out with the name the
  C++ actually reads.
* **`APVProbaList.txt` is not in the release.** `SiStripSimParameters_cfi`
  points `APVProbabilityFile` at it, and `edm::FileInPath` resolves when the
  configuration is translated — before any module exists — so the job aborts
  at startup even though `SiStripDigitizerAlgorithm` opens the file only when
  `APVSaturationFromHIP` is set, and it defaults to false. Pointed at a file
  that does ship. This is the third data file in this flake with that shape;
  see the HF and Castor shower libraries in [MuonGunSim](../MuonGunSim).

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30`:

```bash
cmake -B build -S . -G Ninja
cmake --build build

export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

cmsRun python/write_sim_conditions_cfg.py   # once, writes sim_conditions.db
cmsRun python/muon_gun_digi_cfg.py
python3 python/muon_gun_digi_cfg_check.py
cmsRun python/muon_gun_reco_cfg.py
```
