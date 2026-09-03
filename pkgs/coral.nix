{ stdenv
, lib
, src
, cmake
, ninja
, boost
, xercesc
, sqlite
, libuuid
  # optional: without it CORAL is built without the Frontier backend, and a
  # CondCore job can only reach a local sqlite file
, frontier ? null
, cxxStandard ? "17"
}:

# CORAL (the LCG relational database abstraction layer used by CMSSW's
# CondCore), from CMS's fork. Built with cmake instead of CMT, see
# gen/coral-CMakeLists.txt for the package subset.
stdenv.mkDerivation {
  pname = "coral";
  version = "2.3.21";
  inherit src;

  # The one CORAL defect this build hits: a job that opens a frontier://
  # connection does its work and then aborts with SIGABRT at exit. See the
  # patch header - a static mutex in one plugin library is destroyed before
  # the connection pool in another gets to lock it. patch(1) fails loudly if
  # a future coral-src no longer matches, which is the point of shipping it
  # as a patch rather than a substituteInPlace.
  patches = [ ./coral-frontier-lock-lifetime.patch ];

  nativeBuildInputs = [ cmake ninja ];
  buildInputs = [ boost xercesc sqlite libuuid ] ++ lib.optional (frontier != null) frontier;

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
