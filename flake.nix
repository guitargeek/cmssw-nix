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

  outputs = { self, nixpkgs, nixpkgs-2205, cmssw-src, cmssw-10_6-src, alpaka-src, cms-md5-src, vdt-src, coral-src, ecal-deadchannel-data, ecal-trivialcond-data, magfield-data, heppdt-src, lwtnn-src, dd4hep-src, hls-src }:
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

      # CORAL for CondCore, once per release era
      coral = pkgs.callPackage ./pkgs/coral.nix {
        src = coral-src;
      };

      coral_2205 = pkgs2205.callPackage ./pkgs/coral.nix {
        src = coral-src;
      };

      # standalone Minuit2 from the ROOT 6.24 sources: the 22.05 ROOT was
      # built without the Minuit2 component, but the Hcal local reco needs it
      minuit2_2205 = pkgs2205.callPackage ./pkgs/minuit2.nix {
        src = pkgs2205.root.src;
      };

      heppdt_2205 = pkgs2205.callPackage ./pkgs/heppdt.nix {
        src = heppdt-src;
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

      # Environment for using a CMSSW package: build analyzers against it with
      # cmake and run them with cmsRun (see examples/MyAnalyzer).
      makeUserShell = ps: cmsswPkg: rootPkg: extraPackages: ps.mkShell {
        packages = [
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
      };
    in
    {
      packages.${system} = {
        inherit cms-md5 cmssw root cmssw_10_6_30 coral coral_2205;
        default = cmssw;
      };

      devShells.${system} = {
        default = makeUserShell pkgs cmssw root [ pkgs.onetbb pkgs.fmt coral ];

        cmssw_10_6_30 = makeUserShell pkgs2205 cmssw_10_6_30 pkgs2205.root [ pkgs2205.tbb coral_2205 ];

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
