# Xilinx HLS arbitrary-precision types (ap_int.h / ap_fixed.h): header-only.
# The 20_1-era L1 trigger data formats store their words in these fixed-point
# types, so DataFormats/L1Trigger (and everything that reads trigger objects,
# up to DataFormats/PatCandidates) needs them.
{ lib, stdenvNoCC, src }:

stdenvNoCC.mkDerivation {
  pname = "hls-arbitrary-precision-types";
  version = "unstable";
  inherit src;

  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out/include
    cp -r include/. $out/include/
  '' + lib.optionalString stdenvNoCC.hostPlatform.isDarwin ''
    # The *_special headers forward-declare std::complex rather than include
    # <complex> (a workaround for an HLS-internal parser, per their FIXME).
    # libc++ keeps std in an inline namespace, so the forward declaration
    # declares a second, different std::complex and every use of the name is
    # ambiguous. Include the real thing.
    for f in $out/include/ap_int_special.h $out/include/ap_fixed_special.h; do
      grep -q '^template<typename _Tp> class complex;$' $f \
        || { echo "hls: std::complex forward declaration not found in $f" >&2; exit 1; }
      sed -i '/^namespace std {$/{N;N;s|namespace std {\ntemplate<typename _Tp> class complex;\n}|#include <complex>|}' $f
      grep -q '^#include <complex>$' $f \
        || { echo "hls: could not replace the forward declaration in $f" >&2; exit 1; }
    done
    runHook postInstall
  '';
}
