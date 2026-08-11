# CMSSW on nix

A nix flake that packages a subset of [CMSSW](https://github.com/cms-sw/cmssw)
(`CMSSW_20_1_0_pre2`), built with cmake instead of scram. It is the successor
of the [Arch Linux PKGBUILD experiment](../PKGBUILDs/cmssw): the
`BuildFile.xml` → `CMakeLists.txt` conversion script from there lives on in
[gen/cmssw_cmake.py](gen/cmssw_cmake.py), now driven by a nix derivation.

## What is included

Enough of CMSSW to run `cmsRun` with EDM ROOT file input and output and to
work with electron collections, i.e. the transitive closure of:

* `FWCore` (framework, plugin manager, python configuration, services, ...)
* `IOPool` + `FWStorage` (`PoolSource`, `PoolOutputModule`, storage layer)
* `DataFormats` up to `EgammaCandidates` (`reco::GsfElectron` & friends),
  including the ROOT/reflex dictionaries needed to read and write them

The package list is defined in [gen/config.yml](gen/config.yml); the exact
set of external dependencies is resolved in [gen/CMakeLists.txt](gen/CMakeLists.txt).
Everything comes from nixpkgs except two tiny CMS externals packaged here
(`cms-md5`, alpaka headers). ROOT is rebuilt with C++20 to match CMSSW.

## Usage

```bash
nix build          # builds the cmssw package (takes a while!)
nix develop        # shell with cmsRun, CMSSW libs and headers, cmake, ROOT

# inside the shell, CMSSW_BASE etc. are set up:
echo $CMSSW_BASE   # -> /nix/store/...-cmssw-CMSSW_20_1_0_pre2
```

See [examples/MyAnalyzer](examples/MyAnalyzer) for building and running an
analyzer plugin against this CMSSW installation.

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

* `devShells.build` is for hacking on the CMSSW build itself (all deps, no
  cmssw): run the generator + cmake by hand against a local checkout.
* The Geometry/HLT/Sim/RecoLocal... subsystems of the old Arch config are not
  included, but extending `gen/config.yml` (and the dependency list in
  `pkgs/cmssw.nix` + `gen/CMakeLists.txt`) is all it should take.
