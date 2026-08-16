# ConditionsSqlite

Writes a conditions payload into a **local sqlite database** and reads it
back through the ordinary `PoolDBESSource` path — the first proof that this
build can do conditions at all, and the prerequisite for anything that needs
calibration or alignment constants (digitisation, real-data reconstruction).

Nothing new had to be packaged for this. `PoolDBESSource` and
`PoolDBOutputService` are already registered plugins
(`CondCore/{ESSources,DBOutputService}`), and the CORAL we build ships
`liblcg_SQLiteAccess.so`. The payload used is `BeamSpotObjects`, because
`CondCore/BeamSpotPlugins` — which is what binds the payload type to
`BeamSpotObjectsRcd` — is in the build already.

The two jobs:

* `write_conditions_cfg.py` runs `BeamSpotDBWriter`, which fills a
  `BeamSpotObjects` with deliberately unround values and hands it to
  `PoolDBOutputService::writeOne` under tag `BeamSpotObjects_test`. The
  result is `beamspot.db`.
* `read_conditions_cfg.py` points a `PoolDBESSource` at that file and runs
  `BeamSpotDBReader`, which asks the `EventSetup` for `BeamSpotObjectsRcd`
  and throws unless every value matches to 1e-9. The reader knows nothing
  about sqlite — if it passes, a tag was resolved, CORAL opened the
  database and the payload deserialized, all through the path a real job
  uses against a global tag.

Validated twice, as elsewhere in this repo: the reader asserts in-process,
and `read_conditions_cfg_check.py` re-opens `beamspot.db` with **plain
python `sqlite3`** and checks it has the real conditions schema
(`TAG`/`IOV`/`PAYLOAD`/`GLOBAL_TAG`/...), one tag, one IOV, and a payload
BLOB the IOV actually points at.

This example needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`).

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30`:

```bash
cmake -B build -S . -G Ninja
cmake --build build

export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

cmsRun python/write_conditions_cfg.py
cmsRun python/read_conditions_cfg.py
python3 python/read_conditions_cfg_check.py
```

Expected output:

```
wrote BeamSpotObjectsRcd for run 1: x = 0.0918, y = -0.0374, z = 0.4271, sigmaZ = 3.7215
run 1 event 1: beam spot (0.0918, -0.0374, 0.4271), sigmaZ = 3.7215, xError = 0.01
beam spot payload verified in 3 events
beamspot.db: tag 'BeamSpotObjects_test' (BeamSpotObjects, Run)
  IOV since 1 -> payload 44b8109a24054ad5..., 175 bytes
sqlite conditions readback OK
```

## What this does not do yet

`GLOBAL_TAG` and `GLOBAL_TAG_MAP` exist in the file but are empty: this is a
single tag, not a global tag. Reading a *real* CMS global tag additionally
needs the `frontier_client` external and CORAL's `FrontierAccess` plugin,
neither of which is packaged — our CORAL has the sqlite backend only.
