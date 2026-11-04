# NanoGen

Generates **Z → μμ with Pythia 8** and writes the gen-level nanoAOD tables to
a flat NanoAOD file — the first end-to-end *process → NanoAOD* chain of this
build, and the first stage of the road towards full event simulation.

The chain, all standard CMSSW modules:

* `Pythia8GeneratorFilter` (on-shell Z production, `23:onIfAny = 13`,
  pythia's internal NNPDF 2.3 PDF — no LHAPDF data sets needed),
* `GenParticleProducer` on the unsmeared HepMC product, then the standard
  nano `GenParticlePruner` (`finalGenParticles`) and the `GenPart` flat
  table,
* AK4 gen jets (`InputGenJetsParticleSelector` + `ak4GenJets`) with a
  `GenJet` table,
* the `genWeight` table and `Generator` info table,
* `NanoAODOutputModule` writing `nanogen.root`.

The shipped `nanogen_cff` sequence is deliberately not loaded: it also runs
the Rivet-based particle-level tables and the pat jet-flavour machinery,
neither of which is part of this build.

Validated twice: a `GenZmumuChecker` plugin requires ≥ 80% of the events to
contain a status-1 μ⁺μ⁻ pair within 15 GeV of the Z mass, and
`python/nanogen_cfg_check.py` re-opens `nanogen.root` with **plain ROOT**
(the way an analysis would — no CMSSW) and re-finds the Z peak from the
`GenPart_*` branches.

It runs on both releases: 10_6 generates with Pythia 8.240, 20_1 with
8.317. The one difference in the configuration is the `GenPart` table's
lepton isolation column, which 20_1 computes from miniAOD's packed gen
particles; a job that starts from the generator has none, so the column is
dropped, as the shipped `customizeNanoGEN` does.

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30` (10_6) or
`nix develop .#default` (20_1):

```bash
cmake -B build -S . -G Ninja
cmake --build build

export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

cmsRun python/nanogen_cfg.py
python3 python/nanogen_cfg_check.py
```

Expected output (the exact fractions vary with the seed and the Pythia
version; final-state radiation moves a fraction of the events below the
mass window). On 10_6:

```
173 of 200 events with m(mumu) within 15 GeV of the Z peak
nanogen.root: 200 events, 173 with a dimuon mass at the Z (86%)
nanoAOD readback OK
```

On 20_1: 169 of 200 (84%).
