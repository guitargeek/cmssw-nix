# HepPDT: the particle data table library (with HepPID), from CMS's fork of
# the original LCG sources. Needed by SimGeneral/HepPDTRecord (the
# HepPDTESSource that serves the particle table to the reconstruction).
# The autotools scripts predate modern toolchains; the layout is simple
# enough to compile directly.
{ lib, stdenv, tbb, src }:

stdenv.mkDerivation {
  pname = "heppdt";
  version = "3.04.01";
  inherit src;

  # the CMS fork made the particle table a tbb::concurrent_unordered_map
  buildInputs = [ tbb ];

  buildPhase = ''
    runHook preBuild
    mkdir -p lib
    # defs.h is autoheader boilerplate no header actually uses
    touch include/HepPDT/defs.h
    # HepPID first: HepPDT calls into it, and Mach-O wants every symbol of
    # a library resolved when it is linked. (The install name is what
    # Mach-O records in everything that links it; left at the default it
    # would be the bare file name.)
    for pkg in HepPID HepPDT; do
      $CXX -O2 -fPIC -shared -I include \
        -o lib/lib$pkg.so src/$pkg/*.cc -ltbb \
        ${lib.optionalString stdenv.hostPlatform.isDarwin
          "-Llib $([ $pkg = HepPDT ] && echo -lHepPID) -Wl,-install_name,$out/lib/lib$pkg.so"}
    done
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p $out/lib $out/include
    cp lib/*.so $out/lib/
    cp -r include/HepPDT include/HepPID $out/include/
    rm -rf $out/include/*/CVS $out/include/*/Makefile.*
    runHook postInstall
  '';
}
