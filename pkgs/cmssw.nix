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
# HDF5: the 20_1 EcalTrivialConditionRetriever reads its pulse shapes from it
, hdf5 ? null
# HepMC 3: the 20_1 generator products carry both the HepMC 2 and 3 formats
, hepmc3 ? null
# ML inference externals used by the 20_1 reconstruction: ONNXRuntime (e/gamma
# identification, particle flow) and XGBoost (photon identification)
, onnxruntime ? null
, xgboost ? null
# CORAL (pkgs/coral.nix), needed by CondCore
, coral ? null
# libcurl, used by the 20_1-era CondCore/CondDB (WebUtils)
, curl ? null
# clang binaries + libclang python bindings: the CondFormats serialization
# code (boost-serialization methods for the conditions payload classes) is
# generated at build time by a libclang-based script, like scram does it
, clangTools ? null
, libclangPython ? null
, legacySiteConf ? false
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
    ++ lib.optional (clangTools != null) clangTools;

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
    ++ lib.optional (geant4 != null) geant4
    ++ lib.optional (hdf5 != null) hdf5
    ++ lib.optional (hepmc3 != null) hepmc3
    ++ lib.optionals (onnxruntime != null) [ onnxruntime onnxruntime.dev ]
    ++ lib.optional (xgboost != null) xgboost
    ++ lib.optional (coral != null) coral
    ++ lib.optional (curl != null) curl;

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
    python3 ${../gen/prepare_sources.py} ${version}

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
      ${lib.optionalString (geant4 != null) "-DCMSSW_WITH_GEANT4=ON"} \
      ${lib.optionalString (hdf5 != null) "-DCMSSW_WITH_HDF5=ON"} \
      ${lib.optionalString (hepmc3 != null) "-DCMSSW_WITH_HEPMC3=ON"} \
      ${lib.optionalString (onnxruntime != null) "-DCMSSW_WITH_ONNXRUNTIME=ON"} \
      ${lib.optionalString (xgboost != null) "-DCMSSW_WITH_XGBOOST=ON"} \
      ${lib.optionalString (coral != null) "-DCMSSW_WITH_CORAL=ON"} \
      ${lib.optionalString (curl != null) "-DCMSSW_WITH_CURL=ON"} \
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
    # "cfipython") into each package's python directory, so the standard
    # configuration files can import them. The library manifest maps every
    # built library back to its package.
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
            mkdir -p $out/src/$pkg/python
            for f in $tmp/*.py; do
              # handwritten files win over generated ones
              [ -e $out/src/$pkg/python/$(basename $f) ] || cp $f $out/src/$pkg/python/
            done
          fi
          rm -rf $tmp
        done
      }
      export -f gen_cfis
      export out
      xargs -P 8 -n 2 bash -c 'gen_cfis "$@"' _ < library_manifest.txt
    fi

    # Python directory structure: make e.g. FWCore.ParameterSet.Config
    # importable from $out/python.
    for dir in $out/src/*/*/python; do
      [ -d "$dir" ] || continue
      pkgdir=$(dirname "$dir")
      pkg=$(basename "$pkgdir")
      sub=$(basename "$(dirname "$pkgdir")")
      touch "$dir/__init__.py"
      mkdir -p $out/python/$sub
      ln -s "$dir" $out/python/$sub/$pkg
      touch $out/python/$sub/__init__.py
    done
    touch $out/python/__init__.py

    # Useful scripts (edmDumpEventContent etc.)
    if [ -d $out/src/FWCore/PythonUtilities/scripts ]; then
      for f in $out/src/FWCore/PythonUtilities/scripts/*; do
        ln -s $f $out/bin/$(basename $f)
      done
    fi

    # Register the EDM plugins
    export LD_LIBRARY_PATH=$out/lib''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
    $out/bin/edmPluginRefresh $out/lib

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
    substituteAll ${../gen/setup-hook.sh} $out/nix-support/setup-hook

    runHook postInstall
  '';

  # The automatic shebang patching resolves "#!/usr/bin/env python" to the
  # bare python3 interpreter; the scripts (edmDumpEventContent & friends)
  # need the environment with six/future on the path instead.
  postFixup = ''
    if [ -d $out/src/FWCore/PythonUtilities/scripts ]; then
      for f in $out/src/FWCore/PythonUtilities/scripts/*; do
        if [ -f "$f" ] && head -1 "$f" | grep -q python; then
          sed -i "1s|.*|#!${pythonEnv}/bin/python|" "$f"
        fi
      done
    fi
  '';

  passthru = { inherit pythonEnv; };

  meta = {
    description = "CMS software framework (FWCore + DataFormats subset, cmake-based build)";
    homepage = "https://github.com/cms-sw/cmssw";
    license = lib.licenses.asl20;
    platforms = [ "x86_64-linux" ];
  };
}
