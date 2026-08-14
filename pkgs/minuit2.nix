# Standalone Minuit2, built from the math/minuit2 subproject of the ROOT
# source tree. Needed for the 10_6 era: RecoLocalCalo/HcalRecAlgos (the
# method-2 HBHE pulse-shape fit) uses the Minuit2 C++ API, but the ROOT 6.24
# of nixpkgs 22.05 was built without the Minuit2 component. The subproject
# supports exactly this standalone mode (it copies the few ROOT::Math base
# classes it needs into its own Minuit2Math library).
{ stdenv, cmake, src }:

stdenv.mkDerivation {
  pname = "minuit2-standalone";
  version = "6.24.06";
  inherit src;

  # unpack the full ROOT source, build only math/minuit2 (the standalone
  # mode copies license and mathcore files from the surrounding tree)
  sourceRoot = "root-6.24.06/math/minuit2";

  nativeBuildInputs = [ cmake ];

  cmakeFlags = [
    "-DBUILD_SHARED_LIBS=ON"
    "-Dminuit2_standalone=ON"
    "-DCMAKE_INSTALL_LIBDIR=lib"
  ];

  # Math/Util.h includes mathcore's Math/Types.h (for the veccore define),
  # which the standalone install rules do not copy
  postInstall = ''
    cp ../../mathcore/inc/Math/Types.h $out/include/Minuit2/Math/
  '';
}
