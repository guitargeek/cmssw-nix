# Working on the build

## How a release is put together

A release is two derivations. `pkgs/cmssw.nix` (`cmssw-build_<era>`) is the
build:

1. **prepare** — `gen/prepare` edits the CMSSW sources: what this build
   leaves out and the dependency declarations that go with it
   (`scope.py`), newer externals and compilers than the release was
   written for (`toolchain.py`), clang/libc++/macOS (`portability.py`) and
   bugs in CMSSW (`fixes.py`). Each edit says where it must apply; one that
   changes nothing there is an error, because the code it was written for
   has moved.
2. **generate** — `gen/cmssw_cmake.py` turns the BuildFiles of the packages
   in `gen/config.yml` into CMakeLists, under the top-level
   `gen/CMakeLists.txt`, which defines the scram tools (the externals) as
   `<tool>_LIBRARIES`, `<tool>_INCLUDE_DIRECTORIES` and, for scram's flag
   tools, `<tool>_FLAGS`. A tool a BuildFile uses but the CMakeLists does
   not define stops the configuration, with a package that uses it.
3. **build and install** — CMake and ninja, then the release area: `lib/`,
   `bin/`, `src/`, `python/`, the cfipython files, the plugin cache. A
   plugin that cannot be loaded fails the build.

`pkgs/cmssw-release.nix` (`cmssw_<era>`) is what users get: the build with
the cms-data it reads merged into its release area by links
(`gen/release-with-data.sh`). A change to the data rebuilds that in
seconds; a change to anything the build reads rebuilds the build, for
hours.

The optional externals of a build are one table in `pkgs/cmssw.nix`
(`optionalExternals`), and each release passes the ones it has
(`externals` in `flake.nix`). They are deliberately not `callPackage`
arguments: those are filled in from the package set whenever a package of
that name exists there, which is how the 10_6 build once picked up zstd,
bzip2 and curl without anyone asking for them.

## Checks

```bash
nix flake check                                     # everything; hours from scratch
nix build .#checks.aarch64-darwin.prepare-20_1      # gen/prepare + the generator, minutes
nix flake check --no-build --all-systems            # evaluation only, seconds
```

The `prepare-<era>` checks are the quick test for a change to `gen/prepare`
or the generator, and what the CI workflow (`.github/workflows/check.yml`)
runs, besides evaluating the flake on both systems. Building the releases
and running the examples needs a machine with the hours and the disk for
it.

## Iterating on the build

Every change under `gen/` or `pkgs/` changes the build derivation, and
`nix build` then compiles the release from scratch: hours per attempt,
which is no way to work through a list of compile errors.
`scripts/worktree.sh` keeps a persistent build tree instead and runs the
derivation's own phases in it, in the environment `nix print-dev-env` gives
for the build, so a fix costs an incremental ninja run:

```bash
scripts/worktree.sh 20_1 env        # build environment from the flake
scripts/worktree.sh 20_1 fresh      # unpack, patch, configure
scripts/worktree.sh 20_1 build      # all of it (-k 0), or: build lib/libX.so
scripts/worktree.sh 20_1 install    # into worktree/20_1/out; loads every plugin
scripts/worktree.sh 20_1 run        # the example jobs against that install
scripts/worktree.sh 20_1 run MuonGunSim   # ... or some of them
scripts/worktree.sh 20_1 shell      # a shell with the tree as the release
```

The loop after editing:

* **anything under `gen/`** (a source edit in `gen/prepare`, `config.yml`,
  `CMakeLists.txt`, the generator): `sync`, then `build`. `gen/prepare`
  edits sources in place and is not idempotent, so it never runs on the
  tree itself: `sync` prepares a fresh copy and copies over only what
  differs by content. Unchanged files keep their timestamps, and ninja
  rebuilds only what the edit reaches. (`sync` also regenerates the
  environment: the phases it prints name `gen/` by store path, so a stale
  one would apply the old edits. A new file under `gen/` has to be `git
  add`ed before the flake sees it.)
* **a change to the dependencies** (`flake.nix`, `flake.lock`, `pkgs/`):
  `env`, then `configure --fresh` and `build`. The CMake cache records
  store paths, so it has to go; most of the release recompiles.

`install` also merges the release's cms-data into the tree's release area,
as `pkgs/cmssw-release.nix` does (for 20_1 also the standard sequences',
so that CmsDriverChain runs), and `run` and `shell` use that, with the
setup hooks of the dev shell's extra packages (`cmssw-extras_<era>`: the
Geant4 datasets, the hls4ml models, the PDF sets). The tree
lives in `worktree/<era>` (gitignored; `CMSSW_WORKTREE` moves it) and
takes a few GB per release. Compiling the same phases makes it faithful to
the sandbox build, not identical to it: once the tree is green, `nix build`
and `nix flake check` are what count.

## Keeping rebuilds cheap

A full CMSSW build is hours, so it is worth not losing the result:

```bash
./scripts/build.sh              # build both releases and pin them
./scripts/build.sh 10_6         # just one
```

The `result-*` out-links this creates are indirect gcroots. It also roots
the CMSSW checkouts (~500 MB each), which are *not* part of any output's
runtime closure and are therefore the first thing a `nix-collect-garbage`
takes and among the slowest to fetch again.

To move the binaries to another machine, push them to a
[cachix](https://cachix.org) cache:

```bash
export CACHIX_CACHE=my-cmssw-cache
./scripts/push-cache.sh         # runtime *and* build-time closures
```

The cache is deliberately not declared in `flake.nix`'s `nixConfig`: a
substituter baked into a flake is a trust decision for whoever clones it,
and an unreachable one makes every build print warnings. Consumers opt in
with `cachix use $CACHIX_CACHE`.

## Extending the scope

Which packages can build next, and what holds the rest back:

```bash
python3 gen/rank_blockers.py --src <cmssw source> --config gen/config.yml \
    --with $(nix eval --raw .#packages.<system>.cmssw-build_20_1.configurePhase \
             | grep -o 'CMSSW_WITH_[A-Z0-9_]*' | sort -u) \
    --why PhysicsTools/PatAlgos
```

For every package in the source tree it lists the missing externals in its
dependency closure: the packages that could build already, the blocker
sets by how many packages each holds back, and with `--why <package>` the
dependency chain to each blocker. (`gen/buildfile_model.py` models what
`gen/prepare` does to the dependency graph; keep the two in step.)

Adding packages means `gen/config.yml`, and for a new external its entry in
`optionalExternals` (`pkgs/cmssw.nix`), the release's `externals`
(`flake.nix`) and its tool block in `gen/CMakeLists.txt`. Then the worktree
loop above, `gen/sweep_libs.py` (what the `libsweep` checks run) for the
libraries that link but do not load, and a job under `examples/` that
exercises what was added.

`devShells.build` and `devShells.build_10_6_30` have the build's
dependencies without CMSSW, for running the generator and CMake by hand
against a local checkout; `scripts/worktree.sh` does the same with the
derivation's own phases and is usually the better place to start.

## Linux and static TLS

On Linux, the setup hook raises glibc's static-TLS surplus
(`GLIBC_TUNABLES=glibc.rtld.optional_static_tls`) for the 10_6 release: its
Geant4 10.4 is built multi-threaded with Geant4's default initial-exec TLS
model, which leaves `libG4processes_hadronic.so` with a 1.2 MB `PT_TLS`
segment, more than the default surplus of 512 bytes. Without the bump, the
libraries that pull in Geant4 link fine but fail to `dlopen`. The 20_1
Geant4 is built with the global-dynamic model and does not need it.
