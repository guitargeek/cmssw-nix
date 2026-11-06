{ lib
, stdenv
, src
, version
, cmake
, ninja
, python3
, root
, boost
, tbb
, clhep
, eigen
, tinyxml-2
, fmt
, libuuid
, openssl
, zlib
, jemalloc
, pybind11
, cms-md5
# version-dependent bits: 20_1-era releases use alpaka and cpu_features,
# 10_6-era ones parse the site config with xerces-c and use the pre-2021
# CMS_PATH/SITECONF site config layout.
, configFile ? ../gen/config.yml
, cxxStandard ? "20"
, alpaka-src ? null
, cpu_features ? null
, xercesc ? null
# HepMC 2 + liblzma, needed by SimDataFormats/GeneratorProducts (part of the
# miniAOD-reading closure of the 10_6 config)
, hepmc ? null
, xz
# vdt fast-math headers (scram tool vdt_headers), used by TrackingTools and
# DataFormats/ParticleFlowReco
, vdt ? null
# GSL, used by CalibCalorimetry/HcalAlgos (part of the calo local reco)
, gsl ? null
# standalone Minuit2 (pkgs/minuit2.nix) for ROOT builds without the Minuit2
# component (nixpkgs 22.05); newer ROOTs provide ROOT::Minuit2 themselves
, minuit2 ? null
# reco-chain externals: fastjet (+contrib) for jet clustering, HepPDT for
# the particle data table, lwtnn for the DeepFlavour tagger and the lwtnn
# track classifier, openblas for the MVA trainer
, fastjet ? null
, fastjet-contrib ? null
, heppdt ? null
, lwtnn ? null
, openblas ? null
# DD4hep: the 20_1-era geometry packages build on it
, dd4hep ? null
# Xilinx ap_int/ap_fixed headers (20_1 L1 trigger data formats) and Geant4
# (the HGCal geometry constants use G4 units)
, hls ? null
, geant4 ? null
# the hls4ml model-loading interface: L1Trigger/L1TGlobal's AXOL1TL and
# CICADA conditions (the models are loaded at run time)
, hls4ml-emulator-extras ? null
# utm: the L1 trigger menu library behind the L1TUtm* payloads, which
# L1Trigger/L1TGlobal and HLTrigger/HLTcore need (without it, the payloads
# are pruned)
, utm ? null
# zstd for the streamer file format (IOPool/Streamer, EventFilter/Utilities),
# bzip2 for the Geners archives (Alignment/Geners, JetMETCorrections)
, zstd ? null
, bzip2 ? null
# classlib (DQMNet's sockets) and protobuf (the DQM histogram file format,
# regenerated with the protoc at hand): DQMServices/Core
, classlib ? null
, protobuf ? null
# G4HepEm: SimG4Core/PhysicsLists includes its headers unconditionally
, g4hepem ? null
# HDF5: the 20_1 EcalTrivialConditionRetriever reads its pulse shapes from it
, hdf5 ? null
# HepMC 3: the 20_1 generator products carry both the HepMC 2 and 3 formats
, hepmc3 ? null
# ML inference externals used by the 20_1 reconstruction: ONNXRuntime (e/gamma
# identification, particle flow) and XGBoost (photon identification)
, onnxruntime ? null
, xgboost ? null
# TensorFlow (pkgs/tensorflow-cc.nix): the 20_1 reconstruction's DNNs. Without
# it, gen/prepare_sources.py prunes the TensorFlow users.
, tensorflow-cc ? null
# Tauola++ (pkgs/tauolapp.nix): the tau decays of GeneratorInterface/
# TauolaInterface and NanoAOD's TauSpinner table. Without it both are pruned.
, tauolapp ? null
# Rivet (with YODA) and tinyxml2: GeneratorInterface/RivetInterface's
# particle-level producers, which NanoAOD's MC sequence schedules
, rivet ? null
, yoda ? null
, tinyxml2 ? null
# event generation: Pythia 8 (pkgs/pythia8.nix for 10_6, nixpkgs' for 20_1),
# LHAPDF and libsigc++ (GeneratorInterface/LHEInterface signals) from
# nixpkgs, and HighFive (header-only HDF5 C++ interface, the LHE HDF5 reader
# of 20_1)
, pythia8 ? null
, lhapdf ? null
, libsigcxx ? null
, highfive ? null
# CORAL (pkgs/coral.nix), needed by CondCore
, coral ? null
# libcurl, used by the 20_1-era CondCore/CondDB (WebUtils)
, curl ? null
# nlohmann/json (header-only, scram tool "json"): FWCore/Services'
# DumpDependencyGraph writes the module graph with it, as of 20_1_0_pre4
, nlohmann_json ? null
# clang binaries + libclang python bindings: the CondFormats serialization
# code (boost-serialization methods for the conditions payload classes) is
# generated at build time by a libclang-based script, like scram does it.
# The script runs clang++ only to ask it for its default include paths, so
# clangTools can be null where the stdenv compiler is clang itself.
, clangTools ? null
, libclangPython ? null
, legacySiteConf ? false
# darwin: raises the macOS deployment target of the build (nixpkgs'
# darwinMinVersionHook), propagated so that what is built against the
# release targets the same version
, deploymentTargetHook ? null
# compiler-wrapper hardening flags to turn off (nixpkgs' hardeningDisable);
# whatever is compiled against the release should turn off the same ones
, hardeningDisable ? [ ]
# extra python packages for the runtime environment (e.g. six for 10_6-era
# python config code)
, extraPythonPackages ? (ps: [ ])
# cms-data externals: data files distributed outside the cmssw repository
# (github.com/cms-data/<Subsystem>-<Package>), installed as the package's
# data/ directory like scram does. List of { path = "Subsystem/Package";
# src = <flake input>; }.
, extraData ? [ ]
}:

let
  pythonEnv = python3.withPackages (ps: [ ps.pyyaml ] ++ extraPythonPackages ps);
in
stdenv.mkDerivation {
  pname = "cmssw";
  inherit version src;

  # Note: root must not appear both here and in buildInputs, its setup hook
  # breaks when sourced at two offsets.
  # clangTools comes last so that the stdenv gcc stays the selected compiler.
  nativeBuildInputs = [ cmake ninja pythonEnv ]
    ++ lib.optional (clangTools != null) clangTools
    ++ lib.optional (protobuf != null) protobuf;

  buildInputs = [
    root
    boost
    tbb
    clhep
    eigen
    tinyxml-2
    fmt
    libuuid
    openssl
    zlib
    jemalloc
    pybind11
    python3
    cms-md5
  ] ++ lib.optional (cpu_features != null) cpu_features
    ++ lib.optional (xercesc != null) xercesc
    ++ lib.optionals (hepmc != null) [ hepmc xz ]
    ++ lib.optional (vdt != null) vdt
    ++ lib.optional (gsl != null) gsl
    ++ lib.optional (minuit2 != null) minuit2
    ++ lib.optional (fastjet != null) fastjet
    ++ lib.optional (fastjet-contrib != null) fastjet-contrib
    ++ lib.optional (heppdt != null) heppdt
    ++ lib.optional (lwtnn != null) lwtnn
    ++ lib.optional (openblas != null) openblas
    ++ lib.optional (dd4hep != null) dd4hep
    ++ lib.optional (hls != null) hls
    ++ lib.optional (hls4ml-emulator-extras != null) hls4ml-emulator-extras
    ++ lib.optional (classlib != null) classlib
    ++ lib.optional (utm != null) utm
    ++ lib.optional (zstd != null) zstd
    ++ lib.optional (bzip2 != null) bzip2
    ++ lib.optional (protobuf != null) protobuf
    ++ lib.optional (geant4 != null) geant4
    ++ lib.optional (g4hepem != null) g4hepem
    ++ lib.optional (hdf5 != null) hdf5
    ++ lib.optional (hepmc3 != null) hepmc3
    ++ lib.optionals (onnxruntime != null) [ onnxruntime onnxruntime.dev ]
    ++ lib.optional (xgboost != null) xgboost
    ++ lib.optional (tensorflow-cc != null) tensorflow-cc
    ++ lib.optional (tauolapp != null) tauolapp
    ++ lib.optionals (rivet != null) [ rivet yoda tinyxml2 ]
    ++ lib.optional (coral != null) coral
    ++ lib.optional (curl != null) curl
    ++ lib.optional (nlohmann_json != null) nlohmann_json
    ++ lib.optional (pythia8 != null) pythia8
    ++ lib.optional (lhapdf != null) lhapdf
    ++ lib.optional (libsigcxx != null) libsigcxx
    ++ lib.optional (highfive != null) highfive;

  propagatedBuildInputs = lib.optional (deploymentTargetHook != null) deploymentTargetHook;

  inherit hardeningDisable;

  # We drive cmake manually because of the custom source layout (top-level
  # CMakeLists.txt above the cmssw source tree).
  dontUseCmakeConfigure = true;

  postUnpack = ''
    # Layout expected by the generator: ./cmssw with the sources, top-level
    # CMakeLists.txt next to it.
    mkdir cmssw-build-root
    mv "$sourceRoot" cmssw-build-root/cmssw
    export sourceRoot=cmssw-build-root
  '';

  # After postUnpack, the working directory (sourceRoot) contains the cmssw
  # sources in ./cmssw and the top-level CMakeLists.txt next to it.
  postPatch = ''
    cp ${../gen/CMakeLists.txt} CMakeLists.txt
    cp ${../gen/cmssw_cmake.py} cmssw_cmake.py
    cp ${configFile} config.yml

    # Trim to the plain cmsRun binary, drop the XrdAdaptor dependency and
    # apply version-specific fixups.
    python3 ${../gen/prepare_sources.py} ${version}${lib.optionalString (tensorflow-cc != null) " --with-tensorflow"}${lib.optionalString (tauolapp != null) " --with-tauolapp"}

    ${lib.optionalString (libclangPython != null) ''
      # Generate the conditions serialization code (src/Serialization.cc per
      # CondFormats package), as scram's CondFormats build rules would: the
      # generator clang-parses each package's headers.h and emits the
      # boost-serialization method definitions and instantiations.
      export CMSSW_BASE=$PWD
      export PYTHONPATH=${libclangPython}/site-packages''${PYTHONPATH:+:$PYTHONPATH}
      for pkg in $(python3 ${../gen/list_packages.py} config.yml); do
        case $pkg in
          CondFormats/Serialization) continue;;
          CondFormats/*) ;;
          *) continue;;
        esac
        [ -f cmssw/$pkg/src/headers.h ] || continue
        echo "generating serialization code for $pkg"
        python3 cmssw/CondFormats/Serialization/python/condformats_serialization_generate.py \
          --output src/Serialization.cc --package cmssw/$pkg -- \
          -std=c++${cxxStandard} -I$CMSSW_BASE/cmssw $NIX_CFLAGS_COMPILE
      done
    ''}
  '';

  configurePhase = ''
    runHook preConfigure

    python3 cmssw_cmake.py config.yml

    cmake -B build -S . -G Ninja \
      -DCMAKE_BUILD_TYPE=None \
      -DCMAKE_INSTALL_PREFIX=$out \
      -DCMAKE_INSTALL_LIBDIR=lib \
      -DCMAKE_INSTALL_BINDIR=bin \
      -DCMAKE_INSTALL_RPATH=$out/lib \
      -DCMAKE_INSTALL_RPATH_USE_LINK_PATH=ON \
      -DCMSSW_CXX_STANDARD=${cxxStandard} \
      ${lib.optionalString (alpaka-src != null)
        "-DCMSSW_WITH_ALPAKA=ON -Dalpaka_INCLUDE_DIRECTORIES=${alpaka-src}/include"} \
      ${lib.optionalString (cpu_features != null) "-DCMSSW_WITH_CPU_FEATURES=ON"} \
      ${lib.optionalString (xercesc != null) "-DCMSSW_WITH_XERCESC=ON"} \
      ${lib.optionalString (hepmc != null) "-DCMSSW_WITH_HEPMC=ON"} \
      ${lib.optionalString (vdt != null) "-DCMSSW_WITH_VDT=ON"} \
      ${lib.optionalString (gsl != null) "-DCMSSW_WITH_GSL=ON"} \
      ${lib.optionalString (fastjet != null) "-DCMSSW_WITH_FASTJET=ON"} \
      ${lib.optionalString (heppdt != null) "-DCMSSW_WITH_HEPPDT=ON"} \
      ${lib.optionalString (lwtnn != null) "-DCMSSW_WITH_LWTNN=ON"} \
      ${lib.optionalString (openblas != null) "-DCMSSW_WITH_OPENBLAS=ON"} \
      ${lib.optionalString (dd4hep != null) "-DCMSSW_WITH_DD4HEP=ON"} \
      ${lib.optionalString (hls != null) "-DCMSSW_WITH_HLS=ON"} \
      ${lib.optionalString (hls4ml-emulator-extras != null) "-DCMSSW_WITH_HLS4ML_EMULATOR_EXTRAS=ON"} \
      ${lib.optionalString (classlib != null) "-DCMSSW_WITH_CLASSLIB=ON"} \
      ${lib.optionalString (utm != null) "-DCMSSW_WITH_UTM=ON"} \
      ${lib.optionalString (zstd != null) "-DCMSSW_WITH_ZSTD=ON"} \
      ${lib.optionalString (bzip2 != null) "-DCMSSW_WITH_BZ2LIB=ON"} \
      ${lib.optionalString (protobuf != null) "-DCMSSW_WITH_PROTOBUF=ON"} \
      ${lib.optionalString (geant4 != null) "-DCMSSW_WITH_GEANT4=ON"} \
      ${lib.optionalString (g4hepem != null) "-DCMSSW_WITH_G4HEPEM=ON"} \
      ${lib.optionalString (hdf5 != null) "-DCMSSW_WITH_HDF5=ON"} \
      ${lib.optionalString (hepmc3 != null) "-DCMSSW_WITH_HEPMC3=ON"} \
      ${lib.optionalString (onnxruntime != null) "-DCMSSW_WITH_ONNXRUNTIME=ON"} \
      ${lib.optionalString (xgboost != null) "-DCMSSW_WITH_XGBOOST=ON"} \
      ${lib.optionalString (tensorflow-cc != null) "-DCMSSW_WITH_TENSORFLOW=ON"} \
      ${lib.optionalString (tauolapp != null) "-DCMSSW_WITH_TAUOLAPP=ON"} \
      ${lib.optionalString (rivet != null) "-DCMSSW_WITH_RIVET=ON"} \
      ${lib.optionalString (coral != null) "-DCMSSW_WITH_CORAL=ON"} \
      ${lib.optionalString (curl != null) "-DCMSSW_WITH_CURL=ON"} \
      ${lib.optionalString (pythia8 != null) "-DCMSSW_WITH_PYTHIA8=ON"} \
      ${lib.optionalString (lhapdf != null) "-DCMSSW_WITH_LHAPDF=ON"} \
      ${lib.optionalString (libsigcxx != null) "-DCMSSW_WITH_SIGCPP=ON"} \
      ${lib.optionalString (highfive != null) "-DCMSSW_WITH_HIGHFIVE=ON"} \
      -DCMSSW_VERSION=${version} \
      -DCMSSW_BUILD_BIN=ON \
      -DCMSSW_BUILD_PLUGINS=ON \
      -DCMSSW_BUILD_TEST=OFF

    runHook postConfigure
  '';

  buildPhase = ''
    runHook preBuild
    # cap parallelism: a dozen concurrent CMSSW/dictionary compilations can
    # exhaust the memory of smaller machines
    jobs=$NIX_BUILD_CORES
    if [ "$jobs" -gt 10 ]; then jobs=10; fi
    # -k 0: keep going on errors, so one failed build reports every broken
    # target instead of just the first
    cmake --build build -j $jobs -- -k 0
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    cmake --install build

    # ROOT dictionary auxiliary files: rootmaps and pcms must live next to the
    # libraries.
    find build -name '*.rootmap' -exec cp {} $out/lib \;
    find build -name '*.pcm' -exec cp {} $out/lib \;

    # Install the sources (headers, python configs, scripts) of all packages
    # we built, mimicking a CMSSW release area under $out/src.
    for pkg in $(python3 ${../gen/list_packages.py} config.yml); do
      if [ -d cmssw/$pkg ]; then
        mkdir -p $out/src/$pkg
        cp -r cmssw/$pkg/. $out/src/$pkg/
        rm -rf $out/src/$pkg/test $out/src/$pkg/doc
        find $out/src/$pkg -name CMakeLists.txt -delete
      fi
    done

    # cms-data externals: install as the data/ directory of their package
    ${lib.concatMapStrings (d: ''
      mkdir -p $out/src/${d.path}/data
      cp -r ${d.src}/. $out/src/${d.path}/data/
    '') extraData}

    # Generate the fillDescriptions-based *_cfi.py files (scram's
    # "cfipython"), so the standard configuration files can import them. The
    # library manifest maps every built library back to its package.
    #
    # Like scram, they go into a tree of their own, $out/cfipython/<pkg>,
    # which the package's __init__.py appends to its __path__ (below), and
    # not next to the handwritten files. A handwritten file still wins, by
    # coming first on the path. Mixing the two in one directory cannot work
    # on a case-insensitive filesystem - the default on macOS, the nix store
    # volume included: CalibTracker/SiStripESProducers ships a handwritten
    # SiStripLorentzAngleDepESProducer_cfi.py, the generator writes
    # siStripLorentzAngleDepESProducer_cfi.py, and only one of the two can
    # exist there, while python imports by exact case.
    if [ -x $out/bin/edmWriteConfigs ] && [ -f library_manifest.txt ]; then
      echo "generating cfipython files"
      export LD_LIBRARY_PATH=$out/lib''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
      gen_cfis() {
        target=$1; pkg=$2
        for so in $out/lib/plugin$target.so $out/lib/lib$target.so; do
          [ -f "$so" ] || continue
          tmp=$(mktemp -d)
          ( cd $tmp && $out/bin/edmWriteConfigs -p "$so" > /dev/null 2>&1 ) || true
          # Everything it writes is needed, not only the *_cfi.py: modern
          # modules get a <ModuleType>.py builder next to the <label>_cfi.py,
          # and the cfi imports it. Dropping those makes the generated cfi
          # unimportable (ModuleNotFoundError at cmsRun time).
          if ls $tmp/*.py > /dev/null 2>&1; then
            # (the package needs a python directory for its __init__.py even
            # when it has no handwritten python of its own)
            mkdir -p $out/src/$pkg/python $out/cfipython/$pkg
            for f in $tmp/*.py; do
              # two libraries of one package: the first one's file stays
              [ -e $out/cfipython/$pkg/$(basename $f) ] || cp $f $out/cfipython/$pkg/
            done
          fi
          rm -rf $tmp
        done
      }
      export -f gen_cfis
      export out
      xargs -P 8 -n 2 bash -c 'gen_cfis "$@"' _ < library_manifest.txt
      # and scram's modules.py next to them, which imports every module
      # type of the package (from IOPool.Input.modules import PoolSource)
      for d in $out/cfipython/*/*; do
        types=$(cd $d && for f in *.py; do
          case $f in *_cfi.py|modules.py) ;; *) echo "''${f%.py}" ;; esac
        done)
        [ -n "$types" ] || continue
        for t in $types; do echo "from .$t import $t"; done > $d/modules.py
      done
    fi
    # the cfis of pruned producers that the configuration code imports anyway
    python3 ${../gen/placeholder_cfis.py} $out

    # Python directory structure: make e.g. FWCore.ParameterSet.Config
    # importable from $out/python.
    for dir in $out/src/*/*/python; do
      [ -d "$dir" ] || continue
      pkgdir=$(dirname "$dir")
      pkg=$(basename "$pkgdir")
      sub=$(basename "$(dirname "$pkgdir")")
      touch "$dir/__init__.py"
      # the generated cfi files, after the handwritten ones
      if [ -d $out/cfipython/$sub/$pkg ]; then
        echo "__path__.append('$out/cfipython/$sub/$pkg')" >> "$dir/__init__.py"
      fi
      mkdir -p $out/python/$sub
      ln -s "$dir" $out/python/$sub/$pkg
      touch $out/python/$sub/__init__.py
    done
    touch $out/python/__init__.py

    # Useful scripts (edmDumpEventContent etc., and cmsDriver.py)
    for d in FWCore/PythonUtilities Configuration/Applications; do
      [ -d $out/src/$d/scripts ] || continue
      for f in $out/src/$d/scripts/*; do
        # (the sources do not carry the executable bit; scram sets it)
        chmod +x $f
        ln -s $f $out/bin/$(basename $f)
      done
    done

    # Register the DD4hep factories of the release (the DD4HEP_PLUGIN
    # libraries: the DDCMS XML converters and geometry algorithms the
    # magnetic field and the DD4hep geometry are built with). DD4hep finds
    # them through <library>.components files in its search path, which
    # scram writes with this tool; given an absolute path, it names the
    # library absolutely. They go in a directory of their own, not lib/,
    # where edmPluginRefresh would try to load them.
    ${lib.optionalString (dd4hep != null) ''
      if [ -f dd4hep_plugins.txt ]; then
        mkdir -p $out/dd4hep
        while read -r t; do
          for so in $out/lib/plugin$t.so $out/lib/lib$t.so; do
            [ -f "$so" ] || continue
            ${dd4hep}/bin/listcomponents_dd4hep -o "$out/dd4hep/$(basename "''${so%.so}").components" "$so"
          done
        done < dd4hep_plugins.txt
      fi
    ''}

    # Register the EDM plugins.
    export LD_LIBRARY_PATH=$out/lib''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

    # edmPluginRefresh dlopens every plugin in order to index it, so it needs
    # the same static-TLS surplus that gen/setup-hook.sh gives consumers of
    # this package - the hook applies to people who use the release, not to
    # our own build. Without it every plugin that pulls in Geant4 fails with
    # "cannot allocate memory in static TLS block". Keep the value in step
    # with the one in gen/setup-hook.sh, which explains where it comes from.
    export GLIBC_TUNABLES=glibc.rtld.optional_static_tls=2097152

    # ... and check the result, because edmPluginRefresh reports a plugin it
    # could not load on stderr and then exits 0. That is how the whole of
    # SimG4Core and SimG4CMS once ended up absent from the cache in a build
    # that succeeded: the libraries were there, correct and complete, and
    # cmsRun still said "Unable to find plugin 'OscarMTProducer'". A plugin
    # that cannot be loaded here cannot be loaded by a job either, so it is a
    # build failure and not a warning.
    $out/bin/edmPluginRefresh $out/lib 2>&1 | tee plugin-refresh.log
    if grep -q 'unable to load' plugin-refresh.log; then
      echo "error: the plugin cache is incomplete - these did not load:" >&2
      grep 'unable to load' plugin-refresh.log >&2
      exit 1
    fi

    # Minimal site configuration so that PoolSource works without a real CMS
    # site setup (the setup hook points SITECONFIG_PATH / CMS_PATH here).
    ${if legacySiteConf then ''
      install -Dm644 ${../gen/site-local-config-10_6.xml} \
        $out/SITECONF/local/JobConfig/site-local-config.xml
      install -Dm644 ${../gen/storage-10_6.xml} $out/SITECONF/local/PhEDEx/storage.xml
      substituteInPlace $out/SITECONF/local/JobConfig/site-local-config.xml \
        --subst-var out
    '' else ''
      install -Dm644 ${../gen/site-local-config.xml} $out/siteconf/JobConfig/site-local-config.xml
      install -Dm644 ${../gen/storage.json} $out/siteconf/storage.json
    ''}

    # Environment needed to use this CMSSW install, applied automatically when
    # the package is used in a nix shell.
    mkdir -p $out/nix-support
    substituteAll ${../gen/setup-hook.sh} $out/nix-support/setup-hook${lib.optionalString (extraPythonPackages python3.pkgs != [ ]) ("\n" + ''
      # cmsRun embeds the plain interpreter, and the python modules the
      # release's configuration code imports beyond the standard library
      # (six and future, for 10_6) live in the environment built around it.
      # Whether the embedded interpreter finds that environment by itself
      # depends on how libpython was linked: on darwin the library records
      # the plain interpreter's path as its install name, and the job dies
      # on "No module named 'six'". Name it explicitly.
      echo "addToSearchPath PYTHONPATH ${pythonEnv}/${python3.sitePackages}" >> $out/nix-support/setup-hook
    '')}${lib.optionalString (utm != null) ("
" + ''
      # utm validates L1 menus (L1TUtmTriggerMenuESProducer) against its
      # XML schemas, which it finds through this variable only
      echo "export UTM_XSD_DIR=${utm}/share/utm/xsd" >> $out/nix-support/setup-hook
    '')}

    runHook postInstall
  '';

  # The automatic shebang patching resolves "#!/usr/bin/env python" to the
  # bare python3 interpreter; the scripts (edmDumpEventContent & friends)
  # need the environment with six/future on the path instead.
  postFixup = ''
    for d in FWCore/PythonUtilities Configuration/Applications; do
      [ -d $out/src/$d/scripts ] || continue
      for f in $out/src/$d/scripts/*; do
        if [ -f "$f" ] && head -1 "$f" | grep -q python; then
          sed -i "1s|.*|#!${pythonEnv}/bin/python|" "$f"
        fi
      done
    done
  '';

  passthru = { inherit pythonEnv; };

  meta = {
    description = "CMS software framework (FWCore + DataFormats subset, cmake-based build)";
    homepage = "https://github.com/cms-sw/cmssw";
    license = lib.licenses.asl20;
    platforms = [ "x86_64-linux" "aarch64-darwin" ];
  };
}
