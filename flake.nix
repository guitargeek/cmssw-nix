{
  description = "CMSSW (FWCore + DataFormats subset) packaged for nix, built with cmake instead of scram";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    # Era-appropriate package set for the 10_6 releases (2021/22): gcc 11,
    # ROOT 6.24 (built as C++17, the gcc 11 default), classic TBB 2020.3 with
    # the tbb::task API that old FWCore needs, python 3.9.
    nixpkgs-2205.url = "github:NixOS/nixpkgs/nixos-22.05";

    cmssw-src = {
      url = "github:cms-sw/cmssw/CMSSW_20_1_0_pre2";
      flake = false;
    };

    cmssw-10_6-src = {
      url = "github:cms-sw/cmssw/CMSSW_10_6_30";
      flake = false;
    };

    alpaka-src = {
      url = "github:alpaka-group/alpaka/2.1.1";
      flake = false;
    };

    cms-md5-src = {
      url = "github:cms-externals/md5?ref=cms/1.0.0";
      flake = false;
    };

    vdt-src = {
      url = "github:dpiparo/vdt/v0.4.3";
      flake = false;
    };

    coral-src = {
      url = "github:cms-externals/coral/cms/CORAL_2_3_21py3";
      flake = false;
    };

    # the HTTP transport CORAL's FrontierAccess backend sits on: what CMS
    # conditions use to reach a global tag through the squid hierarchy
    frontier-src = {
      url = "github:fermitools/frontier/v2_8_21";
      flake = false;
    };

    # cms-data externals: BDT weights for the Ecal dead-channel recovery,
    # amplitude/pedestal/time weights for the trivial Ecal conditions
    ecal-deadchannel-data = {
      url = "github:cms-data/RecoLocalCalo-EcalDeadChannelRecoveryAlgos";
      flake = false;
    };
    ecal-trivialcond-data = {
      url = "github:cms-data/CalibCalorimetry-EcalTrivialCondModules";
      flake = false;
    };
    # the field maps the volume-based magnetic field engine interpolates
    magfield-data = {
      url = "github:cms-data/MagneticField-Interpolation";
      flake = false;
    };

    # externals for the reco chain: HepPDT (particle data table) and lwtnn
    # (lightweight NN inference, DeepFlavour + track classifier)
    heppdt-src = {
      url = "github:cms-externals/heppdt/cms/3.04.01";
      flake = false;
    };
    # event generation: the Pythia 8.240 the 10_6 release era was built with
    # (the 8.3 series changed the API the 10_6 Pythia8Interface uses)
    pythia8-src = {
      url = "github:cms-externals/pythia8/cms/240";
      flake = false;
    };
    lwtnn-src = {
      url = "github:lwtnn/lwtnn/v2.9";
      flake = false;
    };

    # DD4hep: the 20_1-era geometry is built on it
    dd4hep-src = {
      url = "github:AIDASoft/DD4hep/v01-31";
      flake = false;
    };

    # Xilinx arbitrary-precision headers: the 20_1 L1 trigger data formats
    # store their words in ap_int/ap_fixed types
    hls-src = {
      url = "github:Xilinx/HLS_arbitrary_Precision_Types";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, nixpkgs-2205, cmssw-src, cmssw-10_6-src, alpaka-src, cms-md5-src, vdt-src, coral-src, ecal-deadchannel-data, ecal-trivialcond-data, magfield-data, heppdt-src, pythia8-src, lwtnn-src, dd4hep-src, hls-src, frontier-src }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      pkgs2205 = nixpkgs-2205.legacyPackages.${system};

      # CMSSW_20_1 needs C++20, so ROOT (and with it rootcling/genreflex, which
      # parse CMSSW headers) must be built with the same standard. nixpkgs
      # builds ROOT with the default C++17.
      root = pkgs.root.overrideAttrs (old: {
        cmakeFlags = old.cmakeFlags ++ [ "-DCMAKE_CXX_STANDARD=20" "-Dclad=OFF" ];
      });

      cms-md5 = pkgs.callPackage ./pkgs/cms-md5.nix {
        src = cms-md5-src;
      };

      cms-md5_10_6 = pkgs2205.callPackage ./pkgs/cms-md5.nix {
        src = cms-md5-src;
      };

      vdt = pkgs2205.callPackage ./pkgs/vdt.nix {
        src = vdt-src;
      };

      vdt_201 = pkgs.callPackage ./pkgs/vdt.nix {
        src = vdt-src;
      };

      libclang-python = pkgs.callPackage ./pkgs/libclang-python.nix { };

      libclang-python_2205 = pkgs2205.callPackage ./pkgs/libclang-python.nix {
        llvmPackages = pkgs2205.llvmPackages_14;
      };

      # The frontier client, once per release era: CORAL's FrontierAccess
      # backend links it, and it is what turns a frontier:// connect string
      # into an HTTP request to the conditions squid hierarchy.
      frontier-client = pkgs.callPackage ./pkgs/frontier-client.nix {
        src = frontier-src;
      };

      frontier-client_2205 = pkgs2205.callPackage ./pkgs/frontier-client.nix {
        src = frontier-src;
      };

      # CORAL for CondCore, once per release era
      coral = pkgs.callPackage ./pkgs/coral.nix {
        src = coral-src;
        frontier = frontier-client;
      };

      coral_2205 = pkgs2205.callPackage ./pkgs/coral.nix {
        src = coral-src;
        frontier = frontier-client_2205;
      };

      # standalone Minuit2 from the ROOT 6.24 sources: the 22.05 ROOT was
      # built without the Minuit2 component, but the Hcal local reco needs it
      minuit2_2205 = pkgs2205.callPackage ./pkgs/minuit2.nix {
        src = pkgs2205.root.src;
      };

      heppdt_2205 = pkgs2205.callPackage ./pkgs/heppdt.nix {
        src = heppdt-src;
      };

      pythia8_2205 = pkgs2205.callPackage ./pkgs/pythia8.nix {
        src = pythia8-src;
        lhapdf = pkgs2205.lhapdf;
      };

      lwtnn_2205 = pkgs2205.callPackage ./pkgs/lwtnn.nix {
        src = lwtnn-src;
      };

      lwtnn_201 = pkgs.callPackage ./pkgs/lwtnn.nix {
        src = lwtnn-src;
      };

      heppdt_201 = pkgs.callPackage ./pkgs/heppdt.nix {
        src = heppdt-src;
      };

      hls = pkgs.callPackage ./pkgs/hls.nix {
        src = hls-src;
      };

      dd4hep = pkgs.callPackage ./pkgs/dd4hep.nix {
        src = dd4hep-src;
        version = "01-31";
        inherit root;
        xercesc = pkgs.xercesc;
      };

      cmssw = pkgs.callPackage ./pkgs/cmssw.nix {
        src = cmssw-src;
        version = "CMSSW_20_1_0_pre2";
        inherit alpaka-src cms-md5 root;
        tbb = pkgs.onetbb;
        cpu_features = pkgs.cpu_features;
        pybind11 = pkgs.python3Packages.pybind11;
        xercesc = pkgs.xercesc;
        curl = pkgs.curl;
        inherit coral;
        clangTools = pkgs.clang;
        libclangPython = libclang-python;
        gsl = pkgs.gsl;
        vdt = vdt_201;
        fastjet = pkgs.fastjet;
        fastjet-contrib = pkgs.fastjet-contrib;
        heppdt = heppdt_201;
        lwtnn = lwtnn_201;
        openblas = pkgs.openblas;
        inherit dd4hep hls;
        geant4 = pkgs.geant4;
        hdf5 = pkgs.hdf5-cpp;
        hepmc = pkgs.hepmc2;
        hepmc3 = pkgs.hepmc3;
        onnxruntime = pkgs.onnxruntime;
        xgboost = pkgs.xgboost;
        # 10_6-only externals for now (callPackage would auto-fill lhapdf and
        # libsigcxx from the unstable package set just because the names exist)
        pythia8 = null;
        lhapdf = null;
        libsigcxx = null;
      };

      # ROOT 6.24 from nixos-22.05 is already built with C++17 (the gcc 11
      # default standard), which matches the 10_6 release era; no override
      # needed.
      cmssw_10_6_30 = pkgs2205.callPackage ./pkgs/cmssw.nix {
        src = cmssw-10_6-src;
        version = "CMSSW_10_6_30";
        cms-md5 = cms-md5_10_6;
        tbb = pkgs2205.tbb;
        pybind11 = pkgs2205.python3Packages.pybind11;
        configFile = ./gen/config-10_6.yml;
        cxxStandard = "17";
        xercesc = pkgs2205.xercesc;
        hepmc = pkgs2205.hepmc2;
        inherit vdt;
        gsl = pkgs2205.gsl;
        minuit2 = minuit2_2205;
        fastjet = pkgs2205.fastjet;
        fastjet-contrib = pkgs2205.fastjet-contrib;
        heppdt = heppdt_2205;
        lwtnn = lwtnn_2205;
        openblas = pkgs2205.openblas;
        coral = coral_2205;
        pythia8 = pythia8_2205;
        lhapdf = pkgs2205.lhapdf;
        libsigcxx = pkgs2205.libsigcxx;
        extraData = [
          { path = "RecoLocalCalo/EcalDeadChannelRecoveryAlgos"; src = ecal-deadchannel-data; }
          { path = "CalibCalorimetry/EcalTrivialCondModules"; src = ecal-trivialcond-data; }
          { path = "MagneticField/Interpolation"; src = magfield-data; }
        ];
        # 20_1-only externals: callPackage would otherwise auto-fill these
        # from the 22.05 package set just because the names exist there
        geant4 = null;
        hdf5 = null;
        hepmc3 = null;
        dd4hep = null;
        hls = null;
        onnxruntime = null;
        xgboost = null;
        clangTools = pkgs2205.llvmPackages_14.clang;
        libclangPython = libclang-python_2205;
        legacySiteConf = true;
        # the 10_6-era python config code still imports six and past (future)
        extraPythonPackages = ps: [ ps.six ps.future ];
      };

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

      # 20_1 wants fmt and the oneAPI TBB; 10_6 the classic TBB, and pythia8
      # for its setup hook (PYTHIA8DATA must point at the xmldoc directory for
      # the generator to start).
      extraPackages_201 = [ pkgs.onetbb pkgs.fmt coral ];
      extraPackages_10_6 = [ pkgs2205.tbb coral_2205 pythia8_2205 ];

      # Environment for using a CMSSW package: build analyzers against it with
      # cmake and run them with cmsRun (see examples/MyAnalyzer).
      makeUserShell = ps: cmsswPkg: rootPkg: extraPackages: ps.mkShell {
        packages = userPackages ps cmsswPkg rootPkg extraPackages;
      };

      # The example jobs, read from the same file examples/run_all.sh reads.
      exampleJobs = builtins.fromJSON (builtins.readFile ./examples/jobs.json);

      # Build one example directory against a release and run its configs.
      # This is examples/run_all.sh done hermetically: the sources come from
      # the store, the environment is exactly the dev shell's, and a failure
      # is a failed derivation rather than a line in a log.
      makeExampleCheck = ps: cmsswPkg: rootPkg: extraPackages: era: job:
        ps.stdenv.mkDerivation {
          name = "cmssw-example-${era}-${job.dir}";
          src = ./examples + "/${job.dir}";

          nativeBuildInputs = [ ps.cmake ps.ninja ];
          buildInputs = userPackages ps cmsswPkg rootPkg extraPackages;

          # The examples drive cmake themselves (they need CMSSW_BASE from the
          # setup hook, which is only set once buildInputs have been sourced).
          dontUseCmakeConfigure = true;

          buildPhase = ''
            runHook preBuild
            # ROOT writes into $HOME on startup
            export HOME=$TMPDIR
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
      makeSweepCheck = ps: cmsswPkg: era:
        ps.runCommand "cmssw-libsweep-${era}"
          { buildInputs = [ cmsswPkg cmsswPkg.pythonEnv ]; }
          ''
            # ROOT's rootmap autoloading complains on stderr about every
            # header it cannot find while loading the dictionaries - hundreds
            # of kilobytes of noise that has nothing to do with whether the
            # library loaded. Keep it, but only show it if something failed.
            python3 ${./gen/sweep_libs.py} ${cmsswPkg}/lib > sweep.log 2> sweep.err || {
              cat sweep.log
              echo "--- stderr ---"
              tail -50 sweep.err
              exit 1
            }
            cat sweep.log
            cp sweep.log $out
          '';
    in
    {
      packages.${system} = {
        inherit cms-md5 cmssw root cmssw_10_6_30 coral coral_2205 pythia8_2205;
        inherit frontier-client frontier-client_2205;
        default = cmssw;
      };

      # `nix flake check` builds and runs the whole example suite for both
      # releases, plus a dlopen sweep over every library. Each example
      # directory is a check of its own, so they build in parallel and a
      # failure names the example that broke.
      checks.${system} =
        let
          check_10_6 = makeExampleCheck pkgs2205 cmssw_10_6_30 pkgs2205.root extraPackages_10_6 "10_6";
          check_201 = makeExampleCheck pkgs cmssw root extraPackages_201 "20_1";
          named = era: mk: map (job: {
            name = "example-${era}-${job.dir}";
            value = mk job;
          }) exampleJobs.${era};
        in
        builtins.listToAttrs (named "10_6" check_10_6 ++ named "20_1" check_201) // {
          libsweep-10_6 = makeSweepCheck pkgs2205 cmssw_10_6_30 "10_6";
          libsweep-20_1 = makeSweepCheck pkgs cmssw "20_1";
        };

      devShells.${system} = {
        default = makeUserShell pkgs cmssw root extraPackages_201;

        cmssw_10_6_30 = makeUserShell pkgs2205 cmssw_10_6_30 pkgs2205.root extraPackages_10_6;

        # Environments for hacking on the CMSSW build itself: all the
        # dependencies, so the generator + cmake can be run by hand against a
        # local cmssw checkout.
        build = pkgs.mkShell {
          inputsFrom = [ cmssw ];
          packages = [ pkgs.git ];
          shellHook = ''
            export ALPAKA_INCLUDE=${alpaka-src}/include
          '';
        };

        build_10_6_30 = pkgs2205.mkShell {
          inputsFrom = [ cmssw_10_6_30 ];
          packages = [ pkgs2205.git ];
        };
      };
    };
}
