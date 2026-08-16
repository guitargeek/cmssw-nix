# Pythia 8.240 (CMS's fork of the 8.2 series the 10_6 releases were built
# against - the 8.3 series changed the API GeneratorInterface/Pythia8Interface
# uses). Built with the LHAPDF6 plugin, so "PDF:pSet = LHAPDF6:<set>" works
# once PDF data sets are on LHAPDF_DATA_PATH; the internal NNPDF 2.3 default
# needs nothing extra.
{ stdenv, src, lhapdf, rsync, cxxStandard ? "17" }:

stdenv.mkDerivation {
  pname = "pythia8";
  version = "8.240";
  inherit src;

  # pythia's own configure script (not autotools): it writes Makefile.inc
  nativeBuildInputs = [ rsync ];
  buildInputs = [ lhapdf ];

  postPatch = ''
    patchShebangs configure bin/
  '';

  configurePhase = ''
    runHook preConfigure
    ./configure \
      --prefix=$out \
      --enable-shared \
      --cxx-common="-O2 -std=c++${cxxStandard} -fPIC -pthread" \
      --with-lhapdf6=${lhapdf}
    runHook postConfigure
  '';

  enableParallelBuilding = true;

  # `make install` uses rsync
  postInstall = ''
    # the xmldoc directory is what PYTHIA8DATA must point to at runtime
    test -f $out/share/Pythia8/xmldoc/Index.xml
    mkdir -p $out/nix-support
    echo "export PYTHIA8DATA=$out/share/Pythia8/xmldoc" > $out/nix-support/setup-hook
  '';
}
