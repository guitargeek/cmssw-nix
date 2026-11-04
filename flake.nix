{
  description = "CMSSW (FWCore + DataFormats subset) packaged for nix, built with cmake instead of scram";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    # Era-appropriate package set for the 10_6 releases (2021/22): gcc 11,
    # ROOT 6.24 (built as C++17, the gcc 11 default), classic TBB 2020.3 with
    # the tbb::task API that old FWCore needs, python 3.9.
    nixpkgs-2205.url = "github:NixOS/nixpkgs/nixos-22.05";

    cmssw-src = {
      url = "github:cms-sw/cmssw/CMSSW_20_1_0_pre4";
      flake = false;
    };

    cmssw-10_6-src = {
      url = "github:cms-sw/cmssw/CMSSW_10_6_30";
      flake = false;
    };

    alpaka-src = {
      url = "github:alpaka-group/alpaka/2.2.0";
      flake = false;
    };

    cms-md5-src = {
      url = "github:cms-externals/md5?ref=cms/1.0.0";
      flake = false;
    };

    # 20_1_0_pre4 moved to the namespaced edm_md5.h of the 2.0.0 branch;
    # 10_6 keeps the original md5.h
    cms-md5-2-src = {
      url = "github:cms-externals/md5?ref=cms/2.0.0";
      flake = false;
    };

    # classlib, for DQMServices/Core (DQMNet); the branch cmsdist builds
    classlib-src = {
      url = "github:cms-externals/classlib/cms/3.1.3";
      flake = false;
    };

    utm-src = {
      url = "gitlab:cms-l1t-utm/utm/utm_0.14.1?host=gitlab.cern.ch";
      flake = false;
    };

    hls4ml-emulator-extras-src = {
      url = "github:cms-hls4ml/hls4mlEmulatorExtras/v1.1.4";
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
    # ... and the same maps in the layout 10_6 reads. Upstream has since
    # merged each grid's per-volume s*/grid.*.bin files into one merged.bin
    # plus index, which the 20_1 engine reads and 10_6 cannot - so 10_6 is
    # pinned to the last commit with the old layout.
    magfield-data-10_6 = {
      url = "github:cms-data/MagneticField-Interpolation/d26df47beb8fbfcf28b9693a14b9bcba3a2a60bc";
      flake = false;
    };
    # the lookup tables and firmware parameters of the Stage-2 muon trigger
    # emulators (BMTF, uGMT, OMTF, EMTF, CPPF)
    l1tmuon-data = {
      url = "github:cms-data/L1Trigger-L1TMuon";
      flake = false;
    };
    # the L1 menus and their prescale and mask tables, for the Global
    # Trigger emulator
    l1tglobal-data = {
      url = "github:cms-data/L1Trigger-L1TGlobal";
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

    # Geant4 10.4.p03, from CMS's fork - the exact version the 10_6 release
    # was built against. This is not a version that can float: SimG4Core and
    # SimG4CMS carry no G4VERSION_NUMBER guards anywhere, so they compile
    # against one Geant4 API and no other. nixpkgs' geant4 is the 11 series,
    # which moved enough of that API to be unusable here.
    geant4-10_4-src = {
      url = "github:cms-externals/geant4?ref=cms/v10.4.3";
      flake = false;
    };

    # G4HepEm, for the 20_1 simulation: SimG4Core/PhysicsLists does not
    # compile without it. Upstream tags by date. See pkgs/g4hepem.nix.
    g4hepem-src = {
      url = "github:mnovak42/g4hepem?ref=20251114";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, nixpkgs-2205, cmssw-src, cmssw-10_6-src, alpaka-src, cms-md5-src, cms-md5-2-src, classlib-src, utm-src, hls4ml-emulator-extras-src, coral-src, ecal-deadchannel-data, ecal-trivialcond-data, magfield-data, magfield-data-10_6, l1tmuon-data, l1tglobal-data, heppdt-src, pythia8-src, lwtnn-src, dd4hep-src, hls-src, frontier-src, geant4-10_4-src, g4hepem-src }:
    let
      systems = [ "x86_64-linux" "aarch64-darwin" ];

      # Everything below is built once per system; the outputs are assembled
      # from it at the end of the file.
      perSystem = system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          inherit (pkgs.stdenv.hostPlatform) isDarwin;

          # nixos-22.05 predates most of the Apple silicon work, and a few of
          # the packages the 10_6 release needs do not build there as shipped.
          # The fixes go in as an overlay, so that everything else in the set
          # (ROOT 6.24 on the patched TBB, above all) is built against them.
          # Linux gets the stock package set, unchanged.
          pkgs2205 =
            if isDarwin then
              import nixpkgs-2205 {
                inherit system;
                overlays = [
                  (final: prev: {
                    # built with LLVM 10 on clang platforms (its test suite
                    # fails with 11+), whose compiler-rt is marked broken
                    # here. The library itself is fine with the default
                    # stdenv; only the tests are not.
                    jemalloc = (prev.jemalloc.override { stdenv = final.stdenv; }).overrideAttrs (_: {
                      doCheck = false;
                    });

                    # declared Linux-only, and links -framework System, which
                    # the SDK this nixpkgs ships does not have (libSystem is
                    # linked by default anyway). Later nixpkgs build the same
                    # sources on darwin.
                    pacparser = prev.pacparser.overrideAttrs (old: {
                      postPatch = (old.postPatch or "") + ''
                        substituteInPlace src/Makefile --replace "-framework System" ""
                      '';
                      meta = old.meta // { platforms = final.lib.platforms.unix; };
                    });

                    # ROOT 6.24's interpreter carries the LLVM 9 clang driver,
                    # which accepts only 10.x macOS deployment targets - it
                    # predates Big Sur - and fails every rootcling run with
                    # "invalid version number in MACOSX_DEPLOYMENT_TARGET=11.0",
                    # the lowest target arm64 has. The relaxed check is the
                    # one later LLVMs have. (At run time too: cling parses the
                    # same variable, and every nix shell exports it.)
                    #
                    # And the C++ standard: nothing in the expression sets one,
                    # so ROOT takes the compiler's default - C++17 for the gcc
                    # 11 of Linux, which is what the 10_6 release and its
                    # dictionaries are written for, but C++14 for the clang 11
                    # of darwin, under which genreflex cannot parse them.
                    root = prev.root.overrideAttrs (old: {
                      cmakeFlags = (old.cmakeFlags or [ ]) ++ [ "-DCMAKE_CXX_STANDARD=17" ];
                      postPatch = (old.postPatch or "") + ''
                        f=interpreter/llvm/src/tools/clang/lib/Driver/ToolChains/Darwin.cpp
                        grep -q 'HadExtra || Major != 10 || Minor >= 100' $f \
                          || { echo "root: macOS version check not where expected" >&2; exit 1; }
                        sed -i 's/HadExtra || Major != 10 || Minor >= 100/HadExtra || Major < 10 || Major >= 100 || Minor >= 100/' $f

                        # cling parses the release's headers at run time with
                        # libc++ in C++17 mode, which drops std::auto_ptr and
                        # the other features C++17 removed - and the 10_6
                        # headers still use them (LHEEventProduct,
                        # GenEventInfoProduct). The compiler and genreflex get
                        # libc++'s switch to keep them (gen/CMakeLists.txt);
                        # cling needs it from the start, since a dictionary
                        # payload's own defines come after <memory> has been
                        # parsed once already.
                        f=interpreter/cling/lib/Interpreter/CIFactory.cpp
                        grep -q 'argvCompile.push_back("--target=arm64-apple-darwin20.3.0");' $f \
                          || { echo "root: cling target setup not where expected" >&2; exit 1; }
                        sed -i 's|argvCompile.push_back("--target=arm64-apple-darwin20.3.0");|&\n    argvCompile.push_back("-D_LIBCPP_ENABLE_CXX17_REMOVED_FEATURES");|' $f

                        # PyROOT loads its C++ backend by bare file name
                        # whenever LD_LIBRARY_PATH or DYLD_LIBRARY_PATH is
                        # set, leaving the search to dyld - which reads only
                        # DYLD_LIBRARY_PATH, and SIP strips that from the
                        # environment of anything started through a protected
                        # binary, /usr/bin/env included. So `import ROOT`
                        # works in the shell and fails in every
                        # "#!/usr/bin/env" script run from it. Load the
                        # backend from ROOT's own lib/ on darwin, which is
                        # what PyROOT already does when neither variable is
                        # set.
                        f=bindings/pyroot/cppyy/cppyy/python/cppyy/__init__.py
                        grep -q "if not any(var in os.environ for var in ('LD_LIBRARY_PATH','DYLD_LIBRARY_PATH')):" $f \
                          || { echo "root: cppyy backend lookup not where expected" >&2; exit 1; }
                        sed -i "s|if not any(var in os.environ for var in ('LD_LIBRARY_PATH','DYLD_LIBRARY_PATH')):|if sys.platform == 'darwin' or not any(var in os.environ for var in ('LD_LIBRARY_PATH','DYLD_LIBRARY_PATH')):|" $f
                      '';
                    });

                    # the classic TBB the 10_6 framework is written against
                    # has no arm64 Mac port; see the patch
                    tbb = prev.tbb.overrideAttrs (old: {
                      patches = (old.patches or [ ]) ++ [ ./pkgs/tbb-2020-darwin-arm64.patch ];
                      makeFlags = (old.makeFlags or [ ]) ++ final.lib.optional final.stdenv.hostPlatform.isAarch64 "arch=arm64";
                    });
                  })
                ];
              }
            else
              nixpkgs-2205.legacyPackages.${system};

          # CMSSW_20_1 needs C++20, so ROOT (and with it rootcling/genreflex, which
          # parse CMSSW headers) must be built with the same standard. nixpkgs
          # builds ROOT with the default C++17.
          root = pkgs.root.overrideAttrs (old: {
            cmakeFlags = old.cmakeFlags ++ [ "-DCMAKE_CXX_STANDARD=20" "-Dclad=OFF" ];
            # On Apple arm64 cling compiles for a hardcoded
            # arm64-apple-darwin20.3.0 (macOS 11.2), and libc++ marks
            # everything newer unavailable for that target - the
            # floating-point std::to_chars behind std::format among them. So
            # any header that formats a float, FWCore/Utilities/Exception.h
            # included, fails to autoparse at run time, and every dictionary
            # that pulls it in with it. Availability markup is meaningless for
            # code JIT-compiled into the running process anyway: what the
            # process has loaded is what there is. Turn it off for cling.
            postPatch = (old.postPatch or "") + pkgs.lib.optionalString isDarwin ''
              substituteInPlace interpreter/cling/lib/Interpreter/CIFactory.cpp \
                --replace-fail 'argvCompile.push_back("--target=arm64-apple-darwin20.3.0");' \
                               'argvCompile.push_back("--target=arm64-apple-darwin20.3.0");
                argvCompile.push_back("-D_LIBCPP_DISABLE_AVAILABILITY");'
            '';
          });

          cms-md5 = pkgs.callPackage ./pkgs/cms-md5.nix {
            src = cms-md5-2-src;
            version = "2.0.0";
          };

          cms-md5_10_6 = pkgs2205.callPackage ./pkgs/cms-md5.nix {
            src = cms-md5-src;
          };

          # pkgs/vdt.nix is written for current nixpkgs (to be upstreamed).
          # CMSSW only uses the inline headers, so 10_6 takes the same build.
          vdt = pkgs.callPackage ./pkgs/vdt.nix { };

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

          # Pythia for 20_1: 8.317, the version cmsdist builds the release
          # with, which is nixpkgs'. The 10_6 recipe's setup hook is added so
          # PYTHIA8DATA points at the xmldoc directory the generator reads at
          # startup.
          pythia8_201 = pkgs.pythia.overrideAttrs (old: {
            postInstall = (old.postInstall or "") + ''
              test -f $out/share/Pythia8/xmldoc/Index.xml
              mkdir -p $out/nix-support
              echo "export PYTHIA8DATA=$out/share/Pythia8/xmldoc" > $out/nix-support/setup-hook
            '';
          });

          # Of the L1 menus, the one the 20_1 Global Trigger emulator's
          # defaults name (simGtStage2Digis, PrescalesVetosFract_cff), with
          # its prescale and mask tables: 11 MB of the repository's 80.
          l1tglobal-menu_201 = pkgs.runCommand "l1tglobal-menu" { } ''
            mkdir -p $out/Luminosity/startup
            for f in L1Menu_Collisions2022_v1_1_0 \
                     UGT_BASE_RS_{PRESCALES,ALGOBX_MASK,FINOR_MASK,VETO_MASK}_L1MenuCollisions2022_v1_1_0; do
              cp ${l1tglobal-data}/Luminosity/startup/$f.xml $out/Luminosity/startup/
            done
          '';

          lwtnn_2205 = pkgs2205.callPackage ./pkgs/lwtnn.nix {
            src = lwtnn-src;
          };

          # Geant4 for the 10_6 simulation. Built against the same pkgs2205.clhep
          # the release links, which callPackage fills in - see pkgs/geant4.nix
          # for why one CLHEP matters.
          geant4_10_4 = pkgs2205.callPackage ./pkgs/geant4.nix {
            src = geant4-10_4-src;
            cxxStandard = "17";
          };

          geant4-data = pkgs2205.callPackage ./pkgs/geant4-data.nix { };

          # nixpkgs builds Geant4 at C++17, which is Geant4's own default. The
          # 20_1 release is C++20 throughout, and dd4hep refuses to build DDG4
          # against a Geant4 whose recorded Geant4_CXX_STANDARD is lower than its
          # own - correctly, since the two share types across that boundary. So
          # the whole 20_1 side takes this one: the release, dd4hep and G4HepEm
          # all compile against the same toolkit at the same standard.
          geant4_201 = pkgs.geant4.overrideAttrs (old: {
            # The particle table and the mutex guarding it are both
            # function-local statics, so they are destroyed at exit in the
            # reverse order of their construction - the mutex first whenever
            # the table came first, which it does in a CMSSW job. The table's
            # destructor then locks a destroyed std::mutex. glibc lets that
            # pass; macOS reports EINVAL, libc++ throws, and every simulation
            # job aborts after its last event. A mutex that is never destroyed
            # cannot be outlived.
            postPatch = (old.postPatch or "") + pkgs.lib.optionalString isDarwin ''
              substituteInPlace source/particles/management/src/G4ParticleTable.cc \
                --replace-fail 'static G4Mutex _instance = G4MUTEX_INITIALIZER;' \
                               'static auto& _instance = *new G4Mutex;'
            '';
            cmakeFlags = (old.cmakeFlags or [ ]) ++ [
              "-DCMAKE_CXX_STANDARD=20"
              # nixpkgs only asks for global-dynamic when it also builds the
              # Python bindings, so the default here is initial-exec. That is the
              # wrong model for this build regardless of what dd4hep demands:
              # initial-exec thread-locals are allocated from the static TLS block
              # at program start, and every CMSSW plugin library - including all of
              # SimG4Core - is dlopened long after that. Geant4 declares a great
              # many G4ThreadLocal variables, so the failure mode is a plugin that
              # loads fine until the block happens to be full and then cannot
              # allocate memory in static TLS.
              "-DGEANT4_BUILD_TLS_MODEL=global-dynamic"
            ];
          });

          # The 11.x datasets for the 20_1 build. nixpkgs packages these, so this
          # only gathers their exports into one hook - see pkgs/geant4-data-11.nix
          # for why depending on them directly does not work.
          geant4-data_201 = pkgs.callPackage ./pkgs/geant4-data-11.nix {
            geant4 = geant4_201;
          };

          # G4HepEm for the 20_1 simulation. Built against the same nixpkgs
          # Geant4 the release links - it compiles Geant4 headers into its own
          # public interface, so the two must be the same toolkit.
          g4hepem = pkgs.callPackage ./pkgs/g4hepem.nix {
            src = g4hepem-src;
            version = "20251114";
            geant4 = geant4_201;
          };

          lwtnn_201 = pkgs.callPackage ./pkgs/lwtnn.nix {
            src = lwtnn-src;
          };

          heppdt_201 = pkgs.callPackage ./pkgs/heppdt.nix {
            src = heppdt-src;
          };

          classlib = pkgs.callPackage ./pkgs/classlib.nix {
            src = classlib-src;
            # classlib's regular expressions are written against PCRE 1, which
            # nixpkgs has dropped as end of life; build it from the 22.05
            # recipe with the current toolchain
            pcre = pkgs.callPackage "${nixpkgs-2205}/pkgs/development/libraries/pcre" {
              pcre = null;
            };
          };

          utm = pkgs.callPackage ./pkgs/utm.nix {
            src = utm-src;
          };

          hls4ml-emulator-extras = pkgs.callPackage ./pkgs/hls4ml-emulator-extras.nix {
            src = hls4ml-emulator-extras-src;
          };

          hls = pkgs.callPackage ./pkgs/hls.nix {
            src = hls-src;
          };

          dd4hep = pkgs.callPackage ./pkgs/dd4hep.nix {
            src = dd4hep-src;
            version = "01-31";
            inherit root;
            xercesc = pkgs.xercesc;
            # explicit, not the callPackage default: DDG4 has to be built against
            # the same C++20 toolkit as the release
            geant4 = geant4_201;
          };

          cmssw = pkgs.callPackage ./pkgs/cmssw.nix {
            src = cmssw-src;
            version = "CMSSW_20_1_0_pre4";
            inherit alpaka-src cms-md5 root;
            tbb = pkgs.onetbb;
            cpu_features = pkgs.cpu_features;
            pybind11 = pkgs.python3Packages.pybind11;
            xercesc = pkgs.xercesc;
            curl = pkgs.curl;
            nlohmann_json = pkgs.nlohmann_json;
            # FWCore/ParameterSet parses doubles with std::from_chars, whose
            # floating-point overloads the system libc++ only has as of
            # macOS 26 - the SDK marks them unavailable below that.
            deploymentTargetHook = if isDarwin then pkgs.darwinMinVersionHook "26.0" else null;
            # nixpkgs builds against libc++ with its "fast" hardening mode on,
            # which turns precondition violations into traps; libstdc++, which
            # CMSSW is developed and validated against, checks none of them.
            # The release has a few that are harmless as written, e.g.
            # SiStripLorentzAngleFakeESSource binding a const double& to
            # element [i] of a vector it leaves empty and never reading it -
            # undefined, but inert with libstdc++ and a SIGTRAP with libc++.
            # Build it the way it is validated.
            hardeningDisable = pkgs.lib.optional isDarwin "libcxxhardeningfast";
            inherit coral;
            # (on darwin the stdenv compiler is clang already, and a second
            # clang wrapper on the PATH could shadow it)
            clangTools = if isDarwin then null else pkgs.clang;
            libclangPython = libclang-python;
            gsl = pkgs.gsl;
            inherit vdt;
            fastjet = pkgs.fastjet;
            fastjet-contrib = pkgs.fastjet-contrib;
            heppdt = heppdt_201;
            lwtnn = lwtnn_201;
            openblas = pkgs.openblas;
            inherit dd4hep hls hls4ml-emulator-extras;
            # DQMServices/Core
            inherit classlib utm;
            protobuf = pkgs.protobuf;
            # the streamer format and the Geners archives
            zstd = pkgs.zstd;
            bzip2 = pkgs.bzip2;
            geant4 = geant4_201;
            inherit g4hepem;
            hdf5 = pkgs.hdf5-cpp;
            hepmc = pkgs.hepmc2;
            hepmc3 = pkgs.hepmc3;
            onnxruntime = pkgs.onnxruntime;
            xgboost = pkgs.xgboost;
            # event generation
            pythia8 = pythia8_201;
            lhapdf = pkgs.lhapdf;
            highfive = pkgs.highfive;
            # 10_6-only (callPackage would auto-fill it from the unstable
            # package set just because the name exists)
            libsigcxx = null;
            # The cms-data externals the 10_6 build carries, and the L1 muon
            # trigger tables (20_1 builds the emulators). These are data
            # files distributed separately from the release - the magnetic field
            # interpolation tables are the ones with teeth, since without them
            # the volume-based field engine cannot be built at all and every
            # example that reconstructs a momentum is stuck with a uniform field.
            extraData = [
              { path = "RecoLocalCalo/EcalDeadChannelRecoveryAlgos"; src = ecal-deadchannel-data; }
              { path = "CalibCalorimetry/EcalTrivialCondModules"; src = ecal-trivialcond-data; }
              { path = "MagneticField/Interpolation"; src = magfield-data; }
              { path = "L1Trigger/L1TMuon"; src = l1tmuon-data; }
              { path = "L1Trigger/L1TGlobal"; src = l1tglobal-menu_201; }
            ];
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
              { path = "MagneticField/Interpolation"; src = magfield-data-10_6; }
            ];
            geant4 = geant4_10_4;
            # 20_1-only externals: callPackage would otherwise auto-fill these
            # from the 22.05 package set just because the names exist there
            hdf5 = null;
            hepmc3 = null;
            highfive = null;
            dd4hep = null;
            hls = null;
            hls4ml-emulator-extras = null;
            classlib = null;
            utm = null;
            protobuf = null;
            onnxruntime = null;
            xgboost = null;
            nlohmann_json = null;
            clangTools = if isDarwin then null else pkgs2205.llvmPackages_14.clang;
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

          # 20_1 wants fmt and the oneAPI TBB; 10_6 the classic TBB; both pythia8
          # for its setup hook (PYTHIA8DATA must point at the xmldoc directory for
          # the generator to start). Both carry a Geant4 and its datasets, but not
          # the same ones: 10_6 links Geant4 10.4 (built here, against the CLHEP
          # the release uses) and 20_1 the nixpkgs Geant4 11. 20_1 also needs
          # classlib, whose headers DQMServices/Core's DQMNet.h includes - so
          # any DQM module or harvester compiled against the release does - and
          # hls, whose ap_int.h DataFormats/HLTReco's trigger object collections
          # include (through the Phase-2 GT candidate), so any module reading
          # HLT filter results does.
          extraPackages_201 = [ pkgs.onetbb pkgs.fmt coral classlib hls pythia8_201 geant4_201 geant4-data_201 ];
          # geant4-data is here for its setup hook alone: the ten G4*DATA
          # variables have to be in the environment of anything that runs the
          # simulation. It deliberately does not go in gen/setup-hook.sh, which
          # both releases share - putting it there would invalidate the 20_1
          # build for a variable only 10_6 uses.
          extraPackages_10_6 = [ pkgs2205.tbb coral_2205 pythia8_2205 geant4_10_4 geant4-data ];

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

          # The example jobs, read from the same file examples/run_all.sh reads.
          exampleJobs = builtins.fromJSON (builtins.readFile ./examples/jobs.json);

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
              src = pkgs.lib.fileset.toSource {
                root = ./examples;
                fileset = pkgs.lib.fileset.unions [
                  (./examples + "/${job.dir}")
                  ./examples/data
                  ./examples/cmake
                  ./examples/common
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
          packages = {
            inherit cms-md5 cmssw root cmssw_10_6_30 coral coral_2205 pythia8_2205;
            inherit geant4_10_4 geant4-data geant4-data_201 g4hepem;
            inherit frontier-client frontier-client_2205;
            default = cmssw;
          };

          # `nix flake check` builds and runs the whole example suite for both
          # releases, plus a dlopen sweep over every library. Each example
          # directory is a check of its own, so they build in parallel and a
          # failure names the example that broke.
          checks =
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

          devShells = {
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
    in
    {
      packages = nixpkgs.lib.genAttrs systems (system: (perSystem system).packages);
      checks = nixpkgs.lib.genAttrs systems (system: (perSystem system).checks);
      devShells = nixpkgs.lib.genAttrs systems (system: (perSystem system).devShells);
    };
}
