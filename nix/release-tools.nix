# Building against a release: the user environment (dev shells) and the
# flake checks that run the examples and load every library.
{ lib }:
rec {
  # What a user of a release needs on top of the release itself, to build
  # an analyzer against it and run it. Shared by the dev shells and the
  # example checks so the two environments cannot drift apart.
  userPackages = ps: cmsswPkg: rootPkg: extraPackages: [
    cmsswPkg
    ps.cmake
    ps.ninja
    rootPkg
    cmsswPkg.pythonEnv
    # headers reachable from CMSSW headers when compiling user code
    ps.boost
    ps.clhep
    ps.eigen
  ] ++ extraPackages;

  # Environment for using a CMSSW package: build analyzers against it with
  # cmake and run them with cmsRun (see examples/MyAnalyzer).
  makeUserShell = ps: cmsswPkg: rootPkg: extraPackages: ps.mkShell {
    # analyzers compile the release's headers: same flags as the release
    hardeningDisable = cmsswPkg.hardeningDisable or [ ];
    # buildInputs rather than packages (= nativeBuildInputs): the
    # release is something analyzers link against, and on darwin it
    # propagates nixpkgs' deployment-target hook, which only works
    # from there. The example checks list it the same way.
    buildInputs = userPackages ps cmsswPkg rootPkg extraPackages;
  };

  # Build one example directory against a release and run its configs.
  # This is examples/run_all.sh done hermetically: the sources come from
  # the store, the environment is exactly the dev shell's, and a failure
  # is a failed derivation rather than a line in a log.
  makeExampleCheck = ps: cmsswPkg: rootPkg: extraPackages: era: job:
    ps.stdenv.mkDerivation {
      name = "cmssw-example-${era}-${job.dir}";
      hardeningDisable = cmsswPkg.hardeningDisable or [ ];
      # The example directory plus the helpers all examples share:
      # data/ (calorimeter pulse shapes — each consumer symlinks
      # data/ to ../data), cmake/ (the common CMakeLists preamble) and
      # common/ (sources compiled by more than one example).
      # (fileset comes from the modern package set; nixos-22.05's lib
      # does not have it, and path filtering is era-independent)
      src = lib.fileset.toSource {
        root = ../examples;
        fileset = lib.fileset.unions [
          (../examples + "/${job.dir}")
          ../examples/data
          ../examples/cmake
          ../examples/common
        ];
      };

      nativeBuildInputs = [ ps.cmake ps.ninja ];
      buildInputs = userPackages ps cmsswPkg rootPkg extraPackages;

      # The examples drive cmake themselves (they need CMSSW_BASE from the
      # setup hook, which is only set once buildInputs have been sourced).
      dontUseCmakeConfigure = true;

      buildPhase = ''
        runHook preBuild
        # ROOT writes into $HOME on startup
        export HOME=$TMPDIR
        cd ${job.dir}
        cmake -B build -S . -G Ninja
        cmake --build build
        runHook postBuild
      '';

      doCheck = true;
      checkPhase = ''
        runHook preCheck
        # without this a failing cmsRun is hidden by the tee that follows
        set -o pipefail
        export LD_LIBRARY_PATH=$PWD/build''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
        edmPluginRefresh $PWD/build
        for cfg in ${ps.lib.escapeShellArgs job.cfgs}; do
          echo "=== $cfg"
          log=$(basename "''${cfg%.py}").log
          cmsRun "$cfg" 2>&1 | tee "$log"
          # an optional <cfg>_check.py validates the job output from
          # outside CMSSW (e.g. reading a produced nanoAOD file with
          # plain ROOT)
          if [ -f "''${cfg%.py}_check.py" ]; then
            python3 "''${cfg%.py}_check.py" 2>&1 | tee -a "$log"
          fi
        done
        runHook postCheck
      '';

      installPhase = ''
        runHook preInstall
        mkdir -p $out
        cp -- *.log $out/
        runHook postInstall
      '';
    };

  # dlopen every library in a release. Catches the unresolved symbols that
  # linking does not: a pruned source file, a missing external, a Fortran
  # common block nobody allocates.
  # (runCommandCC, not runCommand: on darwin the 20_1 release
  # propagates nixpkgs' deployment-target hook, which expects the
  # compiler wrapper's setup to be there)
  makeSweepCheck = ps: cmsswPkg: era:
    ps.runCommandCC "cmssw-libsweep-${era}"
      { buildInputs = [ cmsswPkg cmsswPkg.pythonEnv ]; }
      ''
        # ROOT's rootmap autoloading complains on stderr about every
        # header it cannot find while loading the dictionaries - hundreds
        # of kilobytes of noise that has nothing to do with whether the
        # library loaded. Keep it, but only show it if something failed.
        python3 ${../gen/sweep_libs.py} ${cmsswPkg}/lib > sweep.log 2> sweep.err || {
          cat sweep.log
          echo "--- stderr ---"
          tail -50 sweep.err
          exit 1
        }
        cat sweep.log
        cp sweep.log $out
      '';

  # Prepare a release's sources and generate its CMakeLists, without building
  # anything: the edits of gen/prepare refuse to apply where the code they
  # were written for has changed, and the generator reads every BuildFile in
  # scope. Minutes, where the build itself takes hours.
  makePrepareCheck = ps: build: era:
    ps.runCommand "cmssw-prepare-${era}" { nativeBuildInputs = [ build.pythonEnv ]; } ''
      cp -r ${build.src} cmssw
      chmod -R u+w cmssw
      python3 ${../gen/prepare} ${build.prepareArgs}
      cp ${build.configFile} config.yml
      python3 ${../gen/cmssw_cmake.py} config.yml
      mkdir $out
      cp library_manifest.txt dd4hep_plugins.txt $out/
    '';

  # The setup hooks of a release's extra packages (the dev shell's on top of
  # the release: the Geant4 datasets, the hls4ml models, PYTHIA8DATA, PDF
  # sets), as one hook: what scripts/worktree.sh runs its jobs with.
  makeExtrasHook = ps: era: extraPackages:
    ps.runCommand "cmssw-extras-${era}" { } ''
      mkdir -p $out/nix-support
      # (some hooks, the PDF sets', only register a postHook, which stdenv
      # runs at the end of its setup: run the ones these add)
      echo '_cmssw_n=''${#postHooks[@]}' > $out/nix-support/setup-hook
      for p in ${lib.escapeShellArgs extraPackages}; do
        if [ -f $p/nix-support/setup-hook ]; then
          echo "source $p/nix-support/setup-hook" >> $out/nix-support/setup-hook
        fi
      done
      echo 'for _cmssw_h in "''${postHooks[@]:_cmssw_n}"; do "$_cmssw_h"; done' >> $out/nix-support/setup-hook
    '';
}
