# DD4hep: the detector description toolkit. CMSSW_20_1 builds its geometry
# on it — DetectorDescription/DDCMS and every Geometry/*Builder package need
# it in their main libraries (in the 10_6 era dd4hep was an optional second
# code path that could simply be pruned).
#
# Only the core is built: the Geant4, LCIO, EDM4hep, HepMC3 and GEAR
# extensions are all off by default, so the dependency set stays ROOT +
# boost + xerces-c.
{ stdenv, cmake, root, boost, xercesc, python3, src, version }:

stdenv.mkDerivation {
  pname = "dd4hep";
  inherit version src;

  nativeBuildInputs = [ cmake ];
  buildInputs = [ root boost xercesc python3 ];

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
    # CMSSW only includes DD4hep/ and XML/ headers: build the core alone
    "-DDD4HEP_BUILD_PACKAGES=DDRec"
  ];

  # the ROOT setup hook must not run at two offsets (see pkgs/cmssw.nix)
  dontUseCmakeBuildDir = false;
}
