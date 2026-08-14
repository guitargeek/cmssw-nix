{ stdenv
, lib
, src
, cmake
, ninja
, boost
, xercesc
, sqlite
, libuuid
, cxxStandard ? "17"
}:

# CORAL (the LCG relational database abstraction layer used by CMSSW's
# CondCore), from CMS's fork. Built with cmake instead of CMT, see
# gen/coral-CMakeLists.txt for the package subset.
stdenv.mkDerivation {
  pname = "coral";
  version = "2.3.21";
  inherit src;

  nativeBuildInputs = [ cmake ninja ];
  buildInputs = [ boost xercesc sqlite libuuid ];

  postPatch = ''
    cp ${../gen/coral-CMakeLists.txt} CMakeLists.txt
  '';

  cmakeFlags = [
    "-DCORAL_CXX_STANDARD=${cxxStandard}"
    # CoralKernel dlopens the liblcg_* service libraries; the RPATH makes
    # them discoverable without any environment setup
    "-DCMAKE_INSTALL_RPATH=${placeholder "out"}/lib"
  ];

  meta = {
    description = "LCG CORAL relational database access layer (CMS fork, CondCore subset)";
    homepage = "https://github.com/cms-externals/coral";
    license = lib.licenses.lgpl3;
    platforms = [ "x86_64-linux" ];
  };
}
