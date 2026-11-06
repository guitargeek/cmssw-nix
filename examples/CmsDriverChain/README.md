# CmsDriverChain

A standard Run 3 Monte Carlo production, as `cmsDriver.py` writes it: no
hand-written configuration, only the four commands the release validation
would use for a 2024 single-muon sample
([python/chain.py](python/chain.py)).

| step | cmsDriver `-s` | output |
| --- | --- | --- |
| 1 | `GEN,SIM` (`SingleMuPt10_pythia8_cfi`, 10 events) | `step1.root` |
| 2 | `DIGI:pdigi_valid,L1,DIGI2RAW,HLT:@relval2024` | `step2.root` |
| 3 | `RAW2DIGI,L1Reco,RECO,RECOSIM,PAT` | `step3.root`, `step3_inMINIAODSIM.root` |
| 4 | `NANO` | `step4.root` |

all with `--era Run3_2024 --conditions auto:phase1_2024_realistic
--geometry DB:Extended`. The configurations are the release's standard
sequences in full: the whole Run 3 L1 emulation (CICADA and the EMTF
network included), the 2024 HLT menu, the complete reconstruction with its
TensorFlow and ONNX networks (the tracking DNNs, mkFit, DeepTau), the
alpaka modules on the CPU backend, PAT, and NanoAOD with
its Rivet particle-level and TauSpinner tables.

## What the check does

`nix flake check` (and `examples/run_all.sh`) runs the four
`python/step<N>_offline_cfg.py` jobs. Each one runs `cmsDriver.py` for its
step, loads the configuration it wrote, and runs it **without events and
without the conditions database** (`chain.offline`): the input is replaced
by an `EmptySource`, `maxEvents` set to 0, and the `GlobalTag` ES source
dropped, because the build sandbox has no network.

That is still most of what can go wrong. Constructing the job translates
every parameter of the configuration into its C++ `ParameterSet` — every
`FileInPath` resolved, so every data file the configuration names must be
there — constructs every scheduled module and every ES module, and runs
their `beginJob`: a missing plugin, a missing data file, a parameter the
module does not accept, a model that fails to load all fail the check. What
it cannot see is what needs events or conditions: the physics.

## The full chain

[run_chain.sh](run_chain.sh) runs the same four configurations for real,
conditions from the global tag over Frontier (it needs network access to
`cmsfrontier.cern.ch`), and checks the NanoAOD with plain ROOT
([python/nano_check.py](python/nano_check.py)):

```sh
nix develop .#with-reco-data
examples/CmsDriverChain/run_chain.sh /tmp/chain
```

On an M-series MacBook, 10 events:

| step | time | output |
| --- | --- | --- |
| 1 GEN-SIM | 77 s | 0.2 MB |
| 2 DIGI-L1-DIGI2RAW-HLT | 102 s | 5.5 MB |
| 3 RECO-PAT | 199 s | 4.0 MB RECO, 1.3 MB MiniAOD |
| 4 NANO | 53 s | 1.2 MB, 1254 branches |

All 20 generated muons (the gun fires a pair per event) come out of the
NanoAOD as reconstructed muons, with a median |Δpt|/pt of 1.1%. The jobs
spend most of their time waiting rather than computing (step 3: 52 s of CPU
in 199 s), most likely for the conditions, a couple of thousand payloads a
step fetched one by one from CERN, which a CMS site would serve from its
squid.

Two things to know about it:

* **Frontier without a squid.** The site configuration
  ([gen/site-local-config.xml](../../gen/site-local-config.xml)) connects
  to the CERN servers directly. The e/gamma regression payloads are large,
  and with the client's default timeouts (5 s to connect, 10 s to read)
  step 3 failed on them in two runs out of three; the configuration raises them to
  30 and 60 s. A run can still fail on a dropped connection; run it again.
* **The forward shower libraries.** The HF and Castor shower libraries are
  not on cms-data; step 1 switches them off (`--customise_commands`), as
  [MuonGunSim](../MuonGunSim) does. Nothing in this sample reaches the
  forward calorimeters.

## The data

The standard sequences read some 2 GB of trained models and weight files
from cms-data — b-tagging, e/gamma identification, DeepTau, DeepMET, the
NanoAOD MVAs, the Phase-2 L1 trigger's models that the configuration names
even in a Run 3 job. They are not in the release: `cms-data-reco_201`
([pkgs/cms-data.nix](../../pkgs/cms-data.nix)) is a data area of its own,
the 30 repositories at the versions cmsdist builds 20_1_0_pre4 with, which
this job's check (`"data"` in [jobs.json](../jobs.json)) and the
`with-reco-data` dev shell add to `CMSSW_SEARCH_PATH`.

The release only needs them for these sequences, so nothing else pays for
them: building the release, or any other example, does not fetch them.
