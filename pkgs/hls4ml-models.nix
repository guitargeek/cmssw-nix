# The trained hls4ml models the L1 trigger emulators load at run time, as
# cmsdist builds them: CICADA (the calorimeter anomaly detection, which the
# Run 3 L1 emulation schedules from 2024 on), AXOL1TL (the Global Trigger's
# anomaly detection conditions) and EMTF_NN (the endcap muon track finder's
# displaced-muon pt assignment). Each model is a shared library that
# L1Trigger code opens by file name through hls4ml/emulator.h
# (CICADAModel_v2p1p2.so, GTADModel_v6.so, EMTFnn_v1.so); the setup hook
# puts them on LD_LIBRARY_PATH, where pkgs/hls4ml-emulator-extras.nix looks
# for them.
{ lib, stdenv, hls4ml-emulator-extras, hls, pname, version, src }:

stdenv.mkDerivation {
  inherit pname version src;

  # (the default LD_FLAGS point at lib64/, the emulator extras of cmsdist)
  makeFlags = [
    "EMULATOR_EXTRAS=${hls4ml-emulator-extras}"
    "HLS_ROOT=${hls}"
    "LD_FLAGS=-L${hls4ml-emulator-extras}/lib -lemulator_interface"
  ];
  enableParallelBuilding = true;

  installPhase = ''
    runHook preInstall
    make PREFIX=$out install
    mv $out/lib64 $out/lib
    runHook postInstall
  '';

  setupHook = builtins.toFile "hls4ml-models-hook.sh" ''
    addToSearchPath LD_LIBRARY_PATH @out@/lib
  '';

  meta.platforms = lib.platforms.unix;
}
