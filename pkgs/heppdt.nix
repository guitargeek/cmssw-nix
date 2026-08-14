# HepPDT: the particle data table library (with HepPID), from CMS's fork of
# the original LCG sources. Needed by SimGeneral/HepPDTRecord (the
# HepPDTESSource that serves the particle table to the reconstruction).
# The autotools scripts predate modern toolchains; the layout is simple
# enough to compile directly.
{ stdenv, tbb, src }:

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
    for pkg in HepPDT HepPID; do
      g++ -O2 -fPIC -shared -I include \
        -o lib/lib$pkg.so src/$pkg/*.cc -ltbb
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
