# Example CMSSW analyzer

This is a small example of how to use the nix-packaged CMSSW framework. It is
the updated version of the example from the old Arch Linux packaging attempt:
because we use cmake instead of scram, building a plugin looks a bit
different, but it is not more complicated.

The package structure is the one we know from CMSSW: a `plugins` directory
with the plugin sources and a `python` directory with configuration files.
There are two plugins:

* [plugins/MyElectronProducer.cc](plugins/MyElectronProducer.cc) puts a few
  toy `reco::GsfElectron` into the event. It replaces the "random MiniAOD
  file" of the original example, so that everything is self-contained (no
  grid access on your laptop anyway).
* [plugins/MyAnalyzer.cc](plugins/MyAnalyzer.cc) prints the transverse
  momenta and pseudorapidities of all electrons, exactly as in the original
  example.

And two configurations: [python/write_cfg.py](python/write_cfg.py) runs the
producer and writes `myelectrons.root` with a `PoolOutputModule`, and
[python/read_cfg.py](python/read_cfg.py) reads that file back with a
`PoolSource` and runs the analyzer, which is the full EDM file round trip
that one would do with real data.

## Building and running

Starting from this directory:

```bash
nix develop ../..           # provides cmsRun, the CMSSW libs, cmake, ...

mkdir -p build
cd build
cmake ..
make
edmPluginRefresh .
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$PWD
cd ..

cmsRun python/write_cfg.py  # writes myelectrons.root
cmsRun python/read_cfg.py   # reads it back and prints the electrons
```

You should see the familiar CMSSW output, ending in something like:

```
event 1
  electron pt = 10.1  eta = -1.99
...
```
