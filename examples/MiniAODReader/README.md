# MiniAODReader

Reads a real MiniAOD file from [CMS Open Data](https://opendata.cern.ch)
with the `CMSSW_10_6_30` package of this flake: prints the `pat::Muon`
kinematics, the leading `pat::Jet`s with their DeepCSV b-tag discriminant,
and the `reco::GenParticle` multiplicity of each event.

This example needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`) — the
`pat::` data formats are not part of the `CMSSW_20_1_0_pre2` package.

## Getting a file

Any `RunIISummer20UL16MiniAODv2` MINIAODSIM file works; those datasets were
produced with CMSSW_10_6_30 itself. The Open Data portal proxies its EOS
storage over plain HTTPS (no xrootd needed), e.g. for a 139 MB file from
[record 63401](https://opendata.cern.ch/record/63401):

```bash
curl -fL -o miniaod.root \
  "https://opendata.cern.ch/eos/opendata/cms/mc/RunIISummer20UL16MiniAODv2/RSGravitonToGluonGluon_kMpl01_M_5000_TuneCP5_13TeV_pythia8/MINIAODSIM/106X_mcRun2_asymptotic_v17-v2/2430000/133BFCAB-7D52-7348-A5C9-3E82C0A5BB74.root"
```

(Not every file listed in a record's file index is still present on EOS; if
the download 404s, probe another entry with
`curl -s -o /dev/null -w "%{http_code}" -r 0-15 <url>` first.)

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30`:

```bash
cmake -B build -S . -G Ninja
cmake --build build

# register the plugin so cmsRun can find it
export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

# with miniaod.root in the current directory:
cmsRun python/read_miniaod_cfg.py
```

Expected output, per event:

```
event 1516: 6 muons, 15 jets, 184 gen particles
  pat::Muon pt = 292.951  eta = -1.36604  isGlobal = 0
  ...
  pat::Jet pt = 1449.64  eta = 0.255218  btag(DeepCSV) = 0.155147
  ...
```

The read is complete — every branch of the miniAOD event record has its
dictionary in the package, so there are no missing-dictionary warnings and
nothing needs to be dropped on input.
