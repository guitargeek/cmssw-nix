# Xilinx HLS arbitrary-precision types (ap_int.h / ap_fixed.h): header-only.
# The 20_1-era L1 trigger data formats store their words in these fixed-point
# types, so DataFormats/L1Trigger (and everything that reads trigger objects,
# up to DataFormats/PatCandidates) needs them.
{ stdenvNoCC, src }:

stdenvNoCC.mkDerivation {
  pname = "hls-arbitrary-precision-types";
  version = "unstable";
  inherit src;

  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out/include
    cp -r include/. $out/include/
    runHook postInstall
  '';
}
