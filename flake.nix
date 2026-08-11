{
  description = "CMSSW (FWCore + DataFormats subset) packaged for nix, built with cmake instead of scram";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    cmssw-src = {
      url = "github:cms-sw/cmssw/CMSSW_20_1_0_pre2";
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
  };

  outputs = { self, nixpkgs, cmssw-src, alpaka-src, cms-md5-src }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};

      # CMSSW needs C++20, so ROOT (and with it rootcling/genreflex, which
      # parse CMSSW headers) must be built with the same standard. nixpkgs
      # builds ROOT with the default C++17.
      root = pkgs.root.overrideAttrs (old: {
        cmakeFlags = old.cmakeFlags ++ [ "-DCMAKE_CXX_STANDARD=20" ];
      });

      cms-md5 = pkgs.callPackage ./pkgs/cms-md5.nix {
        src = cms-md5-src;
      };

      cmssw = pkgs.callPackage ./pkgs/cmssw.nix {
        src = cmssw-src;
        version = "CMSSW_20_1_0_pre2";
        inherit alpaka-src cms-md5 root;
        pybind11 = pkgs.python3Packages.pybind11;
      };
    in
    {
      packages.${system} = {
        inherit cms-md5 cmssw root;
        default = cmssw;
      };

      devShells.${system} = {
        # Environment for using CMSSW: build analyzers against it with cmake
        # and run them with cmsRun (see examples/MyAnalyzer).
        default = pkgs.mkShell {
          packages = [
            cmssw
            pkgs.cmake
            pkgs.ninja
            root
            cmssw.pythonEnv
            # headers reachable from CMSSW headers when compiling user code
            pkgs.boost
            pkgs.onetbb
            pkgs.clhep
            pkgs.eigen
            pkgs.fmt
          ];
        };

        # Environment for hacking on the CMSSW build itself: has all the
        # dependencies, so the generator + cmake can be run by hand against a
        # local cmssw checkout.
        build = pkgs.mkShell {
          inputsFrom = [ cmssw ];
          packages = [ pkgs.git ];
          shellHook = ''
            export ALPAKA_INCLUDE=${alpaka-src}/include
          '';
        };
      };
    };
}
