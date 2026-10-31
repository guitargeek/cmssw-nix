# G4HepEm: the compact re-implementation of Geant4's EM physics for e-/e+/gamma
# that CMSSW_20_1 registers as a G4VTrackingManager.
#
# It is not optional decoration for this build. SimG4Core/PhysicsLists includes
# <G4HepEmTrackingManager.hh> and <G4HepEmConfig.hh> from CMSEmStandardPhysics
# and CMSEmStandardPhysicsXS - the EM half of FTFP_BERT_EMM, which is the
# physics list the simulation examples run - so the package does not compile
# without it. Whether G4HepEm is actually *used* at run time is a separate
# switch, g4SimHits.G4HepEmActive.
#
# Upstream tags by date rather than by semantic version. This one carries the
# G4HepEmConfig API CMSEmStandardPhysics.cc calls into
# (SetEnergyLossStepLimitFunctionParameters, SetMinimalMSCStepLimit,
# SetMSCRangeFactor, SetMSCSafetyFactor), which older tags do not all have.
{ stdenv, cmake, geant4, src, version }:

let
  so = stdenv.hostPlatform.extensions.sharedLibrary;
in

stdenv.mkDerivation {
  pname = "g4hepem";
  inherit version src;

  nativeBuildInputs = [ cmake ];
  buildInputs = [ geant4 ];

  cmakeFlags = [
    "-DCMAKE_CXX_STANDARD=20"
    "-DBUILD_TESTING=OFF"
    "-DG4HepEm_BUILD_TESTING=OFF"
    # The CUDA backend is the reason this project exists upstream; here it is
    # only ever the CPU tracking manager, and enabling it would drag in the
    # whole toolkit.
    "-DG4HepEm_CUDA_BUILD=OFF"
    "-DG4HepEm_GEANT4_BUILD=ON"
  ];

  # The four libraries install unversioned; fail here rather than at the CMSSW
  # link step if upstream ever renames them, since gen/CMakeLists.txt looks
  # them up by these names.
  postInstall = ''
    for lib in g4HepEm g4HepEmData g4HepEmInit g4HepEmRun; do
      test -e $out/lib/lib$lib${so} \
        || { echo "g4hepem: expected lib$lib${so} in $out/lib" >&2; ls $out/lib >&2; exit 1; }
    done
    # Headers install into include/G4HepEm/, but CMSSW includes them
    # unprefixed (<G4HepEmTrackingManager.hh>), so that subdirectory - not
    # include/ - is what gen/CMakeLists.txt has to put on the include path.
    test -e $out/include/G4HepEm/G4HepEmTrackingManager.hh \
      || { echo "g4hepem: G4HepEmTrackingManager.hh is not installed" >&2; exit 1; }
  '';

  meta = {
    description = "Compact EM physics for e-/e+/gamma transport in Geant4";
    homepage = "https://github.com/mnovak42/g4hepem";
  };
}
