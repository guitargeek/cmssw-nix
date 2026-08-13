{ stdenvNoCC, src }:

# The vdt fast-math library (github.com/dpiparo/vdt). CMSSW only uses the
# inline header API (scram tool "vdt_headers"), so installing the headers
# under include/vdt is all that is needed.
stdenvNoCC.mkDerivation {
  pname = "vdt";
  version = "0.4.3";
  inherit src;

  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    mkdir -p $out/include/vdt
    cp include/*.h $out/include/vdt/
  '';
}
