# DD4hep: the detector description toolkit. CMSSW_20_1 builds its geometry
# on it — DetectorDescription/DDCMS and every Geometry/*Builder package need
# it in their main libraries (in the 10_6 era dd4hep was an optional second
# code path that could simply be pruned).
#
# The core plus DDG4, the Geant4 bridge. DDG4 is here because
# SimG4Core/Geometry needs it even on the DDD path this flake uses:
# DDG4ProductionCuts declares one constructor taking a DD4hep
# Geant4GeometryMaps::VolumeMap, so <DDG4/Geant4GeometryInfo.h> is included
# unconditionally and the header does not compile without it. LCIO, EDM4hep,
# HepMC3 and GEAR stay off.
{ stdenv, cmake, root, boost, xercesc, python3, geant4, src, version }:

stdenv.mkDerivation {
  pname = "dd4hep";
  inherit version src;

  nativeBuildInputs = [ cmake ];
  buildInputs = [ root boost xercesc python3 geant4 ];

  # The graphics plugin links ROOT::ROOTHistDraw (a ROOT 7 target nixpkgs'
  # ROOT does not export). CMSSW only uses DDCore/DDParsers, so drop it.
  postPatch = ''
    grep -q 'dd4hep_add_plugin(DDCoreGraphics' DDCore/CMakeLists.txt
    sed -i '/dd4hep_add_plugin(DDCoreGraphics/,+2d' DDCore/CMakeLists.txt
  '';

  cmakeFlags = [
    "-DDD4HEP_USE_XERCESC=ON"
    "-DBUILD_TESTING=OFF"
    "-DBUILD_DOCS=OFF"
    "-DDD4HEP_BUILD_EXAMPLES=OFF"
    "-DCMAKE_CXX_STANDARD=20"
    # Off by default. Without it dd4hep does not fail, it prints
    # "Not Using geant4, not building DDG4" and carries on, so the miss
    # only surfaces as a missing libDDG4.so at the CMSSW link step.
    "-DDD4HEP_USE_GEANT4=ON"
  ];

  # DD4HEP_BUILD_PACKAGES is one CMake variable holding a space-separated list
  # (dd4hep calls SEPARATE_ARGUMENTS on it). It cannot go in cmakeFlags, whose
  # entries are word-split by the shell - that silently drops DDG4 and builds
  # only DDRec, which then fails much later as a missing libDDG4.so.
  preConfigure = ''
    cmakeFlagsArray+=("-DDD4HEP_BUILD_PACKAGES=DDRec DDG4")
  '';

  # the ROOT setup hook must not run at two offsets (see pkgs/cmssw.nix)
  dontUseCmakeBuildDir = false;
}
