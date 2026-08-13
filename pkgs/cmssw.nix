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
, legacySiteConf ? false
# extra python packages for the runtime environment (e.g. six for 10_6-era
# python config code)
, extraPythonPackages ? (ps: [ ])
}:

let
  pythonEnv = python3.withPackages (ps: [ ps.pyyaml ] ++ extraPythonPackages ps);
in
stdenv.mkDerivation {
  pname = "cmssw";
  inherit version src;

  # Note: root must not appear both here and in buildInputs, its setup hook
  # breaks when sourced at two offsets.
  nativeBuildInputs = [ cmake ninja pythonEnv ];

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
    ++ lib.optional (vdt != null) vdt;

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
    cmake --build build -j $jobs
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
