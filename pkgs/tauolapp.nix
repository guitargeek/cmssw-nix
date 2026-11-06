# Tauola++, the tau decay library, with TauSpinner (scram tool "tauolapp"),
# built as cmsdist's tauolapp.spec does. GeneratorInterface/TauolaInterface
# needs it for its plugins, and NanoAOD's MC sequence schedules the
# TauSpinner table (tauSpinnerTable), which computes spin weights with it.
{ lib, stdenv, fetchurl, gfortran, hepmc2, pythia8, lhapdf, boost }:

stdenv.mkDerivation rec {
  pname = "tauolapp";
  version = "1.1.8";

  src = fetchurl {
    url = "https://tauolapp.web.cern.ch/tauolapp/resources/TAUOLA.${version}/TAUOLA.${version}-LHC.tar.gz";
    hash = "sha256-P3NOipZ2goacyiwf/r0+BVViYTxAhTzIGCDYtmaAXtU=";
  };

  nativeBuildInputs = [ gfortran ];
  buildInputs = [ hepmc2 pythia8 lhapdf boost ];

  configureFlags = [
    "--without-hepmc3"
    "--with-hepmc=${hepmc2}"
    "--with-pythia8=${pythia8}"
    "--with-lhapdf=${lhapdf}"
  ] ++ lib.optional stdenv.hostPlatform.isDarwin "--enable-static";
  env = {
    CPPFLAGS = "-I${boost.dev}/include";
  } // lib.optionalAttrs stdenv.hostPlatform.isDarwin {
    # The Fortran library and the C++ interface library call into each
    # other, which Linux shared libraries allow; on darwin leave the
    # symbols to be found at load time, as cmsdist does.
    LDFLAGS = "-Wl,-undefined,dynamic_lookup";
  };

  # one make at a time: the sub-makes share make.inc's objects
  enableParallelBuilding = false;

  # The Fortran library and the C++ libraries share Fortran COMMON blocks
  # (the particle masses, PARMAS; the decay tables, ...), which each of them
  # also defines. ELF resolves every reference to one copy; a darwin dylib
  # binds its own references to its own copy at link time, so the C++ side
  # initialises one copy and the Fortran code reads another - Tauola stops
  # the process on the first decay ("STOP IN APKMAS, WRONG IDENT= 0", exit
  # code 0). Link the five libraries into one, where the definitions merge,
  # under each of their names.
  postInstall = lib.optionalString stdenv.hostPlatform.isDarwin ''
    cd $out/lib
    libs="TauolaFortran TauolaCxxInterface TauolaTauSpinner TauolaHepMC TauolaHEPEVT"
    $CXX -dynamiclib -o libTauola.dylib -install_name $out/lib/libTauola.dylib \
      -Wl,-all_load $(for l in $libs; do echo lib$l.a; done) \
      -L${lib.getLib gfortran.cc}/lib -lgfortran -Wl,-undefined,dynamic_lookup
    for l in $libs; do
      rm -f lib$l.dylib lib$l.0.dylib lib$l.a lib$l.la
      ln -s libTauola.dylib lib$l.dylib
    done
  '';

  meta = {
    description = "Tau lepton decay library with TauSpinner";
    homepage = "https://tauolapp.web.cern.ch";
    license = lib.licenses.gpl3Only;
    platforms = lib.platforms.unix;
  };
}
