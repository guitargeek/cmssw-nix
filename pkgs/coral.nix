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

    # The service libraries are dlopened by bare file name. On Linux that
    # search includes the RUNPATH of CoralKernel, which is set to $out/lib
    # below; dyld does not consult rpaths for a bare name, only for an
    # @rpath-relative one - so say that, in the branch CORAL already keeps
    # for macOS.
    sed -i '/^#ifdef __APPLE__/,/^#else/ s|( "liblcg_" + libraryName|( "@rpath/liblcg_" + libraryName|' \
      CoralKernel/src/PluginManager.cpp
    grep -q '"@rpath/liblcg_" + libraryName' CoralKernel/src/PluginManager.cpp \
      || { echo "coral: the macOS dlopen branch is not where expected" >&2; exit 1; }

    # MessageStream overloads operator<< for libstdc++'s internal manipulator
    # types (std::_Setw and friends), keyed on __GNUC__ - which clang defines
    # too, while its libc++ has no such types. The generic operator<< the
    # class also has covers the manipulators either way; key the overloads
    # on the library they belong to. (sed, as above: the 22.05 stdenv this
    # also builds with has no substituteInPlace --replace-fail.)
    sed -i 's|^#elif defined (__GNUC__)|#elif defined (__GLIBCXX__)|' CoralBase/CoralBase/MessageStream.h
    grep -q '^#elif defined (__GLIBCXX__)' CoralBase/CoralBase/MessageStream.h \
      || { echo "coral: MessageStream.h manipulator block not where expected" >&2; exit 1; }
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
    platforms = [ "x86_64-linux" "aarch64-darwin" ];
  };
}
