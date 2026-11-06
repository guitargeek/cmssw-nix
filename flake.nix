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
    # the hls4ml models the L1 emulation loads at run time (the versions of
    # cmsdist's CICADA.spec, AXOL1TL.spec and EMTF_NN.spec for 20_1)
    cicada-src = {
      url = "github:cms-hls4ml/CICADA/1.4.0";
      flake = false;
    };
    axol1tl-src = {
      url = "github:cms-hls4ml/AXOL1TL/v6.0.4";
      flake = false;
    };
    emtf-nn-src = {
      url = "github:cms-hls4ml/EMTF_NN/v1.0.2";
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
    # the pixel hit resolution histograms the fast simulation smears its
    # tracker hits with
    fastsim-rechit-data = {
      url = "github:cms-data/FastSimulation-TrackingRecHitProducer";
      flake = false;
    };
    # the pixel cluster templates, from which the fast simulation's pixel
    # hit smearing takes its cluster shapes
    sipixel-templates-data = {
      url = "github:cms-data/CalibTracker-SiPixelESProducers";
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

  outputs = { self, nixpkgs, nixpkgs-2205, cmssw-src, cmssw-10_6-src, alpaka-src, cms-md5-src, cms-md5-2-src, classlib-src, utm-src, hls4ml-emulator-extras-src, cicada-src, axol1tl-src, emtf-nn-src, coral-src, ecal-deadchannel-data, ecal-trivialcond-data, magfield-data, magfield-data-10_6, l1tmuon-data, l1tglobal-data, fastsim-rechit-data, sipixel-templates-data, heppdt-src, pythia8-src, lwtnn-src, dd4hep-src, hls-src, frontier-src, geant4-10_4-src, g4hepem-src, ... }@inputs:
    let
      systems = [ "x86_64-linux" "aarch64-darwin" ];

      # Everything below is built once per system; the outputs are assembled
      # from it at the end of the file.
      perSystem = system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          inherit (pkgs.stdenv.hostPlatform) isDarwin;

          # The 10_6 era's package set: on darwin with the fixes of
          # nix/darwin-2205-overlay.nix, on Linux the stock one.
          pkgs2205 =
            if isDarwin then
              import nixpkgs-2205 {
                inherit system;
                overlays = [ (import ./nix/darwin-2205-overlay.nix) ];
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

          # The cms-data of the standard Run 3 sequences, outside the release
          # (pkgs/cms-data.nix), for examples/CmsDriverChain: the models and
          # weight files of the reconstruction, PAT and NanoAOD, at the
          # versions cmsdist's data/cmsswdata.txt gives for CMSSW_20_1_0_pre4
          # (pkgs/cms-data.json; scripts/update-cms-data.py moves them to
          # another release). L1TGlobal is the release's input (the same
          # commit as cmsdist's V00-04-00); the release installs only the
          # 2022 menu of it.
          cms-data-reco_201 = pkgs.callPackage ./pkgs/cms-data.nix {
            name = "cms-data-reco-20_1";
            repos = pkgs.lib.mapAttrsToList (path: r: {
              inherit path;
              src = pkgs.fetchFromGitHub {
                owner = "cms-data";
                repo = builtins.replaceStrings [ "/" ] [ "-" ] path;
                rev = r.tag;
                inherit (r) hash;
              };
            }) (builtins.fromJSON (builtins.readFile ./pkgs/cms-data.json))
            ++ [ { path = "L1Trigger/L1TGlobal"; src = l1tglobal-data; } ];
          };

          # Tauola++ with TauSpinner (cmsdist's tauolapp 1.1.8), for
          # GeneratorInterface/TauolaInterface and NanoAOD's TauSpinner table
          tauolapp = pkgs.callPackage ./pkgs/tauolapp.nix {
            pythia8 = pythia8_201;
            hepmc2 = pkgs.hepmc2;
          };

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

          # Of the pixel templates, one 3.8 T barrel and one forward template of
          # the 2021 set, which the muon gun's FastSim job maps onto every
          # module: 2 MB of the repository's 65.
          sipixel-templates_201 = pkgs.runCommand "sipixel-templates" { } ''
            mkdir -p $out/templates_38T_2021_IOV0
            for n in 1009 1016; do
              cp ${sipixel-templates-data}/templates_38T_2021_IOV0/template_summary_zp$n.out $out/templates_38T_2021_IOV0/
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

          hls4ml-model = pname: version: src: pkgs.callPackage ./pkgs/hls4ml-models.nix {
            inherit hls4ml-emulator-extras hls pname version src;
          };
          cicada = hls4ml-model "CICADA" "1.4.0" cicada-src;
          axol1tl = hls4ml-model "AXOL1TL" "6.0.4" axol1tl-src;
          emtf-nn = hls4ml-model "EMTF_NN" "1.0.2" emtf-nn-src;

          hls = pkgs.callPackage ./pkgs/hls.nix {
            src = hls-src;
          };

          # nixpkgs' TensorFlow is the binary wheel (pinned to a python it
          # has one for: the C++ libraries inside do not depend on it)
          tensorflow-cc = pkgs.callPackage ./pkgs/tensorflow-cc.nix {
            wheel = pkgs.python313Packages.tensorflow-bin;
          };

          # One protobuf in the process, TensorFlow's: its libraries carry
          # protobuf 6.31.1 (the release's version too) on abseil 20250814,
          # and export protobuf's inline code as weak definitions, which
          # dyld coalesces with those of any other protobuf loaded - with
          # nixpkgs' 6.36 next to it, loading both crashes in the static
          # initializers. Same version and abseil, and the coalescing is
          # harmless. onnxruntime links protobuf too (its protoc is a build
          # tool of its own, and it builds its own abseil from the source).
          abseil-cpp-tf = pkgs.abseil-cpp_202508;
          protobuf-tf = pkgs.protobuf_31.override { abseil-cpp = abseil-cpp-tf; };
          onnxruntime-tf = (pkgs.onnxruntime.override {
            protobuf = protobuf-tf;
            abseil-cpp = abseil-cpp-tf;
            # the C++ library is all CMSSW uses
            pythonSupport = false;
          }).overrideAttrs (old: {
            cmakeFlags = map (f:
              if pkgs.lib.hasPrefix "-DONNX_CUSTOM_PROTOC_EXECUTABLE" f
              then "-DONNX_CUSTOM_PROTOC_EXECUTABLE:STRING=${pkgs.lib.getExe protobuf-tf}"
              else f) old.cmakeFlags;
          });

          dd4hep = pkgs.callPackage ./pkgs/dd4hep.nix {
            src = dd4hep-src;
            version = "01-31";
            inherit root;
            xercesc = pkgs.xercesc;
            # explicit, not the callPackage default: DDG4 has to be built against
            # the same C++20 toolkit as the release
            geant4 = geant4_201;
          };

          cmssw-build_201 = pkgs.callPackage ./pkgs/cmssw.nix {
            src = cmssw-src;
            version = "CMSSW_20_1_0_pre4";
            inherit alpaka-src cms-md5 root;
            tbb = pkgs.onetbb;
            pybind11 = pkgs.python3Packages.pybind11;
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
            # (on darwin the stdenv compiler is clang already, and a second
            # clang wrapper on the PATH could shadow it)
            clangTools = if isDarwin then null else pkgs.clang;
            libclangPython = libclang-python;
            externals = {
              inherit (pkgs) cpu_features xercesc curl nlohmann_json gsl fastjet fastjet-contrib
                openblas zstd bzip2 hepmc3 xgboost rivet yoda lhapdf highfive;
              inherit coral vdt dd4hep hls hls4ml-emulator-extras classlib utm g4hepem tensorflow-cc tauolapp;
              heppdt = heppdt_201;
              lwtnn = lwtnn_201;
              protobuf = protobuf-tf;
              geant4 = geant4_201;
              hdf5 = pkgs.hdf5-cpp;
              hepmc = pkgs.hepmc2;
              onnxruntime = onnxruntime-tf;
              tinyxml2 = pkgs.tinyxml-2;
              pythia8 = pythia8_201;
            };
          };

          # ROOT 6.24 from nixos-22.05 is already built with C++17 (the gcc 11
          # default standard), which matches the 10_6 release era; no override
          # needed.
          cmssw-build_10_6 = pkgs2205.callPackage ./pkgs/cmssw.nix {
            src = cmssw-10_6-src;
            version = "CMSSW_10_6_30";
            cms-md5 = cms-md5_10_6;
            tbb = pkgs2205.tbb;
            pybind11 = pkgs2205.python3Packages.pybind11;
            configFile = ./gen/config-10_6.yml;
            cxxStandard = "17";
            externals = {
              inherit (pkgs2205) xercesc gsl fastjet fastjet-contrib openblas lhapdf libsigcxx
                zstd bzip2 curl;
              inherit vdt;
              hepmc = pkgs2205.hepmc2;
              minuit2 = minuit2_2205;
              heppdt = heppdt_2205;
              lwtnn = lwtnn_2205;
              coral = coral_2205;
              pythia8 = pythia8_2205;
              geant4 = geant4_10_4;
            };
            clangTools = if isDarwin then null else pkgs2205.llvmPackages_14.clang;
            libclangPython = libclang-python_2205;
            legacySiteConf = true;
            # the 10_6-era python config code still imports six and past (future)
            extraPythonPackages = ps: [ ps.six ps.future ];
          };

          # The cms-data every release carries (pkgs/cms-data.nix), merged
          # into its release area (pkgs/cmssw-release.nix). The magnetic field
          # interpolation tables are the ones with teeth: without them the
          # volume-based field engine cannot be built at all, and every
          # example that reconstructs a momentum is stuck with a uniform
          # field. 20_1 also carries the L1 muon trigger tables and menu (it
          # builds the emulators) and the fast simulation's pixel resolutions
          # and templates.
          cms-data_201 = pkgs.callPackage ./pkgs/cms-data.nix {
            name = "cms-data-20_1";
            repos = [
              { path = "RecoLocalCalo/EcalDeadChannelRecoveryAlgos"; src = ecal-deadchannel-data; }
              { path = "CalibCalorimetry/EcalTrivialCondModules"; src = ecal-trivialcond-data; }
              { path = "MagneticField/Interpolation"; src = magfield-data; }
              { path = "L1Trigger/L1TMuon"; src = l1tmuon-data; }
              { path = "L1Trigger/L1TGlobal"; src = l1tglobal-menu_201; }
              { path = "FastSimulation/TrackingRecHitProducer"; src = fastsim-rechit-data; }
              { path = "CalibTracker/SiPixelESProducers"; src = sipixel-templates_201; }
            ];
          };
          cms-data_10_6 = pkgs.callPackage ./pkgs/cms-data.nix {
            name = "cms-data-10_6";
            repos = [
              { path = "RecoLocalCalo/EcalDeadChannelRecoveryAlgos"; src = ecal-deadchannel-data; }
              { path = "CalibCalorimetry/EcalTrivialCondModules"; src = ecal-trivialcond-data; }
              { path = "MagneticField/Interpolation"; src = magfield-data-10_6; }
            ];
          };

          # A release: a build with cms-data merged in.
          mkRelease = build: data: pkgs.callPackage ./pkgs/cmssw-release.nix { inherit build data; };
          cmssw = mkRelease cmssw-build_201 [ cms-data_201 ];
          cmssw_10_6_30 = mkRelease cmssw-build_10_6 [ cms-data_10_6 ];

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
          extraPackages_201 = [ pkgs.onetbb pkgs.fmt coral classlib hls pythia8_201 geant4_201 geant4-data_201 cicada axol1tl emtf-nn pkgs.lhapdf.pdf_sets.NNPDF31_nnlo_hessian_pdfas ];
          # geant4-data is here for its setup hook alone: the ten G4*DATA
          # variables have to be in the environment of anything that runs the
          # simulation. It deliberately does not go in gen/setup-hook.sh, which
          # both releases share - putting it there would invalidate the 20_1
          # build for a variable only 10_6 uses. cicada, axol1tl and emtf-nn
          # likewise: the L1 emulation finds its hls4ml models on
          # LD_LIBRARY_PATH. And the NNPDF3.1 set on LHAPDF_DATA_PATH, which
          # NanoAOD's TauSpinner table initialises LHAPDF with.
          extraPackages_10_6 = [ pkgs2205.tbb coral_2205 pythia8_2205 geant4_10_4 geant4-data ];

          # The cms-data example jobs can ask for on top of their release's
          # ("data" in jobs.json): they run against a release with it merged in.
          exampleData = { cms-data-reco = cms-data-reco_201; };

          inherit (import ./nix/release-tools.nix { inherit (pkgs) lib; })
            makeUserShell makeExampleCheck makeSweepCheck makePrepareCheck makeExtrasHook;

          # The example jobs, read from the same file examples/run_all.sh reads.
          exampleJobs = builtins.fromJSON (builtins.readFile ./examples/jobs.json);


          # The releases, by era: everything the outputs below are generated
          # from. Each era gets a package, a dev shell (both also under
          # cmssw_<era>), a check per example directory of jobs.json and a
          # dlopen sweep.
          releases = {
            "20_1" = { ps = pkgs; build = cmssw-build_201; data = [ cms-data_201 ]; package = cmssw; root = root; extraPackages = extraPackages_201; };
            "10_6" = { ps = pkgs2205; build = cmssw-build_10_6; data = [ cms-data_10_6 ]; package = cmssw_10_6_30; root = pkgs2205.root; extraPackages = extraPackages_10_6; };
          };
          forEras = f: builtins.listToAttrs (map (era: f era releases.${era}) (builtins.attrNames releases));
          shellOf = r: makeUserShell r.ps r.package r.root r.extraPackages;
          # the release an example job runs against: its era's, with the
          # cms-data the job asks for merged in
          releaseFor = r: job:
            if job ? data then mkRelease r.build (r.data ++ map (d: exampleData.${d}) job.data) else r.package;
          cmssw-with-reco-data = mkRelease cmssw-build_201 [ cms-data_201 cms-data-reco_201 ];
        in
        {
          packages = {
            inherit cms-md5 cmssw root cmssw_10_6_30 coral coral_2205 pythia8_2205;
            inherit geant4_10_4 geant4-data geant4-data_201 g4hepem;
            inherit frontier-client frontier-client_2205;
            cms-data_20_1 = cms-data_201;
            cms-data-reco_20_1 = cms-data-reco_201;
            inherit cms-data_10_6;
            "cmssw_20_1-with-reco-data" = cmssw-with-reco-data;
            default = cmssw;
          } // forEras (era: r: { name = "cmssw_${era}"; value = r.package; })
            // forEras (era: r: { name = "cmssw-build_${era}"; value = r.build; })
            // forEras (era: r: { name = "cmssw-extras_${era}"; value = makeExtrasHook r.ps era r.extraPackages; });

          # `nix flake check` builds and runs the whole example suite for both
          # releases, plus a dlopen sweep over every library. Each example
          # directory is a check of its own, so they build in parallel and a
          # failure names the example that broke.
          checks = builtins.foldl' (a: b: a // b) { } (map (era:
            let r = releases.${era}; in
            builtins.listToAttrs (map (job: {
              name = "example-${era}-${job.dir}";
              value = makeExampleCheck r.ps (releaseFor r job) r.root r.extraPackages era job;
            }) exampleJobs.${era}) // {
              "libsweep-${era}" = makeSweepCheck r.ps r.package era;
              "prepare-${era}" = makePrepareCheck r.ps r.build era;
            }) (builtins.attrNames releases));

          devShells = {
            default = shellOf releases."20_1";
            cmssw_10_6_30 = shellOf releases."10_6";

            # with the cms-data of the standard Run 3 sequences (some 2 GB):
            # what cmsDriver.py's RECO, PAT and NANO steps read
            with-reco-data = makeUserShell pkgs cmssw-with-reco-data root extraPackages_201;

            # Environments for hacking on the CMSSW build itself: all the
            # dependencies, so the generator + cmake can be run by hand against a
            # local cmssw checkout.
            build = pkgs.mkShell {
              inputsFrom = [ cmssw-build_201 ];
              packages = [ pkgs.git ];
              shellHook = ''
                export ALPAKA_INCLUDE=${alpaka-src}/include
              '';
            };

            build_10_6_30 = pkgs2205.mkShell {
              inputsFrom = [ cmssw-build_10_6 ];
              packages = [ pkgs2205.git ];
            };
          } // forEras (era: r: { name = "cmssw_${era}"; value = shellOf r; });
        };
    in
    {
      packages = nixpkgs.lib.genAttrs systems (system: (perSystem system).packages);
      checks = nixpkgs.lib.genAttrs systems (system: (perSystem system).checks);
      devShells = nixpkgs.lib.genAttrs systems (system: (perSystem system).devShells);
    };
}
