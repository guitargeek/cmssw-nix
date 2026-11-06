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
# liblzma, for HepMC 2 (externals.hepmc)
, xz
# version-dependent bits
, configFile ? ../gen/config.yml
, cxxStandard ? "20"
# alpaka headers (20_1-era): CMSSW_WITH_ALPAKA, the serial backend
, alpaka-src ? null
# The optional externals, by the name in optionalExternals below: whatever
# a release passes here goes into buildInputs and switches on its tool block
# in gen/CMakeLists.txt (CMSSW_WITH_<flag>). Only what is passed is used:
# these are not callPackage arguments, which would be filled in from the
# package set just because a package of that name exists there.
, externals ? { }
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
}:

let
  pythonEnv = python3.withPackages (ps: [ ps.pyyaml ] ++ extraPythonPackages ps);

  # The optional externals, in the order they go into buildInputs: the name
  # in `externals`, the CMSSW_WITH_<flag> switch of its tool block in
  # gen/CMakeLists.txt (null: none, the package is found through another
  # one's block or by the compiler wrapper alone), and what it contributes
  # to buildInputs.
  optionalExternals = [
    { name = "cpu_features"; flag = "CPU_FEATURES"; }
    # the 10_6-era site config parser
    { name = "xercesc"; flag = "XERCESC"; }
    # HepMC 2, with liblzma: SimDataFormats/GeneratorProducts
    { name = "hepmc"; flag = "HEPMC"; inputs = p: [ p xz ]; }
    # the vdt fast-math functions (TrackingTools, ParticleFlowReco)
    { name = "vdt"; flag = "VDT"; }
    # CalibCalorimetry/HcalAlgos
    { name = "gsl"; flag = "GSL"; }
    # a standalone Minuit2 (pkgs/minuit2.nix), for ROOT builds without it
    { name = "minuit2"; flag = null; }
    # jet clustering
    { name = "fastjet"; flag = "FASTJET"; }
    { name = "fastjet-contrib"; flag = null; }
    # the particle data table
    { name = "heppdt"; flag = "HEPPDT"; }
    # the DeepFlavour tagger and the lwtnn track classifier
    { name = "lwtnn"; flag = "LWTNN"; }
    # the MVA trainer
    { name = "openblas"; flag = "OPENBLAS"; }
    # the 20_1-era geometry
    { name = "dd4hep"; flag = "DD4HEP"; }
    # Xilinx ap_int/ap_fixed: the 20_1 L1 trigger data formats
    { name = "hls"; flag = "HLS"; }
    # the hls4ml model interface: the L1 emulation's trained models
    { name = "hls4ml-emulator-extras"; flag = "HLS4ML_EMULATOR_EXTRAS"; }
    # DQMServices/Core (DQMNet's sockets)
    { name = "classlib"; flag = "CLASSLIB"; }
    # the L1 menu library: the L1TUtm* payloads, L1TGlobal, HLTcore
    { name = "utm"; flag = "UTM"; }
    # the streamer file format, and the Geners archives
    { name = "zstd"; flag = "ZSTD"; }
    { name = "bzip2"; flag = "BZ2LIB"; }
    # the DQM histogram file format, regenerated with this protoc (also in
    # nativeBuildInputs)
    { name = "protobuf"; flag = "PROTOBUF"; }
    { name = "geant4"; flag = "GEANT4"; }
    # SimG4Core/PhysicsLists includes its headers unconditionally (20_1)
    { name = "g4hepem"; flag = "G4HEPEM"; }
    # the 20_1 EcalTrivialConditionRetriever reads its pulse shapes from it
    { name = "hdf5"; flag = "HDF5"; }
    # the 20_1 generator products carry both HepMC formats
    { name = "hepmc3"; flag = "HEPMC3"; }
    # the reconstruction's networks (20_1)
    { name = "onnxruntime"; flag = "ONNXRUNTIME"; inputs = p: [ p p.dev ]; }
    { name = "xgboost"; flag = "XGBOOST"; }
    # without it, gen/prepare prunes the TensorFlow users
    { name = "tensorflow-cc"; flag = "TENSORFLOW"; }
    # the tau decays and NanoAOD's TauSpinner table; pruned without it
    { name = "tauolapp"; flag = "TAUOLAPP"; }
    # GeneratorInterface/RivetInterface (with YODA and tinyxml2)
    { name = "rivet"; flag = "RIVET"; }
    { name = "yoda"; flag = null; }
    { name = "tinyxml2"; flag = null; }
    # CondCore
    { name = "coral"; flag = "CORAL"; }
    # CondCore/CondDB's WebUtils
    { name = "curl"; flag = "CURL"; }
    # header-only, scram tool "json": FWCore/Services' DumpDependencyGraph
    { name = "nlohmann_json"; flag = null; }
    # event generation; libsigc++ for 10_6's LHEInterface signals, HighFive
    # for the 20_1 LHE HDF5 reader
    { name = "pythia8"; flag = "PYTHIA8"; }
    { name = "lhapdf"; flag = "LHAPDF"; }
    { name = "libsigcxx"; flag = "SIGCPP"; }
    { name = "highfive"; flag = "HIGHFIVE"; }
  ];

  presentExternals = map (e: {
    inherit (e) flag;
    inputs = (e.inputs or (p: [ p ])) externals.${e.name};
  }) (lib.filter (e: externals ? ${e.name}) optionalExternals);

  # an external by name, or null when the release has none
  external = name: externals.${name} or null;

  # what gen/prepare is run with (also by the flake's prepare checks)
  prepareArgs = version
    + lib.optionalString (externals ? tensorflow-cc) " --with-tensorflow"
    + lib.optionalString (externals ? tauolapp) " --with-tauolapp";
  tensorflow-cc = external "tensorflow-cc";
  tauolapp = external "tauolapp";
  protobuf = external "protobuf";
  dd4hep = external "dd4hep";
  utm = external "utm";
in
assert lib.all (n: lib.any (e: e.name == n) optionalExternals) (lib.attrNames externals);
# The build of a release, without the cms-data it reads: pkgs/cmssw-release.nix
# adds that, and is what users get.
stdenv.mkDerivation {
  pname = "cmssw-build";
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
  ] ++ lib.concatMap (e: e.inputs) presentExternals;

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
    python3 ${../gen/prepare} ${prepareArgs}

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
      ${lib.concatMapStrings (e: "-DCMSSW_WITH_${e.flag}=ON ") (lib.filter (e: e.flag != null) presentExternals)} \
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

  passthru = { inherit pythonEnv prepareArgs configFile; };

  meta = {
    description = "The CMS offline software, built with CMake instead of scram";
    homepage = "https://github.com/cms-sw/cmssw";
    license = lib.licenses.asl20;
    platforms = [ "x86_64-linux" "aarch64-darwin" ];
  };
}
