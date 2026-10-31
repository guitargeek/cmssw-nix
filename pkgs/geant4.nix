# Geant4 10.4.p03, from CMS's fork - the detector simulation SimG4Core and
# SimG4CMS are written against.
#
# The version is not negotiable. Nothing in SimG4Core or SimG4CMS is guarded
# by G4VERSION_NUMBER, so the code compiles against exactly one Geant4 API;
# nixpkgs carries the 11 series, which renamed and moved enough of it to be
# unusable. Hence this build rather than the stock package.
#
# Two settings have to agree with the CMSSW build or things break in ways that
# survive linking:
#
#   * CLHEP. Geant4 vendors a copy, but CMSSW links the system CLHEP directly
#     (HepMC, the magnetic field, SimDataFormats all pass CLHEP types across
#     the boundary). Two CLHEPs in one process means two sets of static random
#     engines and two definitions of every Hep3Vector. GEANT4_USE_SYSTEM_CLHEP
#     keeps it to one.
#   * The C++ standard, for the usual ABI reasons - 17 here, matching the
#     10_6 release.
{ lib
, stdenv
, src
, cmake
, clhep
, xercesc
, expat
, zlib
, cxxStandard ? "17"
}:

stdenv.mkDerivation {
  pname = "geant4";
  version = "10.4.3";
  inherit src;

  nativeBuildInputs = [ cmake ];
  buildInputs = [ clhep xercesc expat zlib ];

  # 10.4 recognises a Mac only on x86_64: on any other clang Mac the
  # multi-threaded build stops at "No Threading model technology supported
  # for this platform", although the pthread code path it would take is
  # plain POSIX. Widen the three platform tests to every clang Mac.
  postPatch = lib.optionalString stdenv.hostPlatform.isDarwin ''
    for f in source/global/management/include/G4Threading.hh \
             source/global/management/include/tls.hh \
             source/processes/electromagnetic/dna/management/src/G4MemStat.cc; do
      grep -q 'defined(__MACH__) && defined(__clang__) && defined(__x86_64__)' $f \
        || { echo "geant4: platform test not found in $f" >&2; exit 1; }
      sed -i 's/defined(__MACH__) \&\& defined(__clang__) \&\& defined(__x86_64__)/defined(__MACH__) \&\& defined(__clang__)/' $f
    done
  '';


  cmakeFlags = [
    "-DCMAKE_BUILD_TYPE=Release"
    "-DBUILD_SHARED_LIBS=ON"
    "-DBUILD_STATIC_LIBS=OFF"
    "-DGEANT4_BUILD_CXXSTD=${cxxStandard}"

    # CMS runs the simulation multi-threaded, and SimG4Core/Application is
    # written against G4MTRunManager.
    "-DGEANT4_BUILD_MULTITHREADED=ON"

    # Off, as CMS builds it - and this one is load-bearing, not a tuning
    # choice. It drops -DG4VERBOSE, and SimG4Core/PhysicsLists does not
    # compile with that macro defined: MonopoleTransportation.cc prints
    # `noCalls` inside two #ifdef G4VERBOSE blocks, and no such variable is
    # declared anywhere in the class or in Geant4 10.4. That dead reference
    # can only have survived in the release because the Geant4 CMSSW_10_6 was
    # built against had verbose code compiled out.
    "-DGEANT4_BUILD_VERBOSE_CODE=OFF"

    # The datasets are a separate derivation (pkgs/geant4-data.nix): this
    # build has no network, and pinning ~620 MB of physics data by hash is
    # something a fixed-output derivation does properly and an ExternalProject
    # download during the build does not.
    "-DGEANT4_INSTALL_DATA=OFF"

    "-DGEANT4_USE_SYSTEM_CLHEP=ON"
    "-DGEANT4_USE_SYSTEM_EXPAT=ON"
    "-DGEANT4_USE_SYSTEM_ZLIB=ON"

    # GDML, so the geometry can be written out and read back; it is also what
    # SimG4Core/PrintGeomInfo dumps. Needs xerces-c.
    "-DGEANT4_USE_GDML=ON"

    # No visualisation drivers: they would pull in X11, OpenGL, Qt and motif
    # for a toolkit that only ever runs batch here.
    "-DGEANT4_USE_OPENGL_X11=OFF"
    "-DGEANT4_USE_XM=OFF"
    "-DGEANT4_USE_RAYTRACER_X11=OFF"
    "-DGEANT4_USE_QT=OFF"
  ] ++ lib.optionals stdenv.hostPlatform.isDarwin [
    # libc++ drops the C++17-deprecated library features outright where
    # libstdc++ keeps them, and 10.4 still uses std::mem_fun_ref (INCL),
    # among others. libc++ keeps them on request; this is the switch for the
    # libc++ of the 22.05 package set (the per-feature macros came later).
    "-DCMAKE_CXX_FLAGS=-D_LIBCPP_ENABLE_CXX17_REMOVED_FEATURES"
  ];

  # The TLS model is left at Geant4's multi-threaded default of initial-exec,
  # which is what makes the toolkit's thread-local statics fast - and what
  # forces the static-TLS surplus that gen/setup-hook.sh raises via
  # GLIBC_TUNABLES. Building global-dynamic instead would make this package
  # self-sufficient but slow down the hottest code in the simulation. If the
  # surplus set there ever stops covering this build, the number to compare
  # against is the PT_TLS memsz below, not a guess.
  postInstall = ''
    mkdir -p $out/nix-support

    # Report the static-TLS demand of this build, so a mismatch with the
    # surplus in gen/setup-hook.sh shows up in the build log rather than as
    # "cannot allocate memory in static TLS block" at dlopen time.
    for lib in $out/lib/libG4processes*.so* $out/lib/libG4track*.so*; do
      [ -f "$lib" ] || continue
      echo "TLS $(basename $lib): $(
        readelf -lW "$lib" 2>/dev/null | awk '$1 == "TLS" {print $6; exit}'
      )"
    done
  '';

  # Geant4 installs a geant4make/geant4.sh that expects to be sourced from its
  # own tree; find_package(Geant4) is what the CMSSW build uses, and cmake
  # finds Geant4Config.cmake through CMAKE_PREFIX_PATH on its own.
  enableParallelBuilding = true;

  meta = {
    description = "Geant4 10.4.p03 (CMS fork), the toolkit CMSSW_10_6 simulates with";
    homepage = "https://geant4.web.cern.ch";
    platforms = lib.platforms.linux ++ lib.platforms.darwin;
  };
}
