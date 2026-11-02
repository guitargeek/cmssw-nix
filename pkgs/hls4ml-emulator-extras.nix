# hls4mlEmulatorExtras: the interface CMSSW's L1 trigger emulators use to
# load hls4ml-generated models (hls4ml/emulator.h, plus the small
# libemulator_interface library behind it). L1Trigger/L1TGlobal needs it to
# compile its AXOL1TL and CICADA anomaly-detection conditions; the models
# themselves (the AXOL1TL and CICADA externals) are loaded at run time, only
# by menus that use those conditions.
{ lib, stdenv, src }:

stdenv.mkDerivation {
  pname = "hls4ml-emulator-extras";
  version = "1.1.4";
  inherit src;

  buildPhase = ''
    runHook preBuild
    $CXX -O2 -fPIC -std=c++17 -shared -I include/hls4ml \
      -o libemulator_interface.so src/hls4ml/emulator.cc \
      ${lib.optionalString stdenv.hostPlatform.isDarwin
        "-Wl,-install_name,$out/lib/libemulator_interface.so"}
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p $out/lib
    cp libemulator_interface.so $out/lib/
    cp -r include $out/include
    runHook postInstall
  '';
}
