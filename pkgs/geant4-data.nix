# The Geant4 10.4 physics datasets: cross sections, atomic transition and
# nuclear level data that the toolkit reads at run time rather than compiling
# in. Geant4's own CMake can download these during the build
# (GEANT4_INSTALL_DATA=ON), which a nix build cannot do - so they are fetched
# here as ordinary fixed-output derivations and pointed at with the ten
# environment variables the toolkit looks for.
#
# Versions and md5 sums come from cmake/Modules/Geant4DatasetDefinitions.cmake
# in the 10.4.3 sources; each tarball's sha256 below was checked against that
# md5 when it was pinned. Getting a version wrong here does not fail the
# build - it fails at run time, usually as a physics process quietly finding
# no data, so they are worth keeping exactly in step with the toolkit.
{ lib, stdenvNoCC, fetchurl }:

let
  base = "https://cern.ch/geant4-data/datasets";

  # name (as the directory Geant4 expects) / version / tarball / env var
  datasets = [
    { name = "G4NDL";              version = "4.5";   file = "G4NDL";              var = "G4NEUTRONHPDATA";   sha256 = "13nzvig8dx2yy0gc663a1jxk829xz1byzir9hayg525742jjiafb"; }
    { name = "G4EMLOW";            version = "7.3";   file = "G4EMLOW";            var = "G4LEDATA";          sha256 = "0km1vdlvbvwlnyzy4q2vq2d5ms919g2h9yb6snvrvc379zrsffjq"; }
    { name = "PhotonEvaporation";  version = "5.2";   file = "G4PhotonEvaporation"; var = "G4LEVELGAMMADATA"; sha256 = "07rdzkrvra24xryfzl2rldhvzgpzr8vc7j8rr9zjlyw26s6pyq43"; }
    { name = "RadioactiveDecay";   version = "5.2";   file = "G4RadioactiveDecay"; var = "G4RADIOACTIVEDATA"; sha256 = "0pdgw81k01lll2v2flapxw0wml65cs5ckhqmpqb16a3hkpc3ih4r"; }
    { name = "G4NEUTRONXS";        version = "1.4";   file = "G4NEUTRONXS";        var = "G4NEUTRONXSDATA";   sha256 = "1zd8fg55q436q8vr85njdsvis5jg5m086qmjcpfhs1pbsxl8icsp"; }
    { name = "G4PII";              version = "1.3";   file = "G4PII";              var = "G4PIIDATA";         sha256 = "09p92rk1sj837m6n6yd9k9a8gkh6bby2bfn6k0f3ix3m4s8as9b2"; }
    { name = "RealSurface";        version = "2.1.1"; file = "G4RealSurface";      var = "G4REALSURFACEDATA"; sha256 = "0l3gs0nlp10cjlwiln3f72zfch0av2g1r8m2ny9afgvwgbwiyj4h"; }
    { name = "G4SAIDDATA";         version = "1.1";   file = "G4SAIDDATA";         var = "G4SAIDXSDATA";      sha256 = "0zzdl1yjpa1br248xa34yankc395rng61zjh529128xn7nldk353"; }
    { name = "G4ABLA";             version = "3.1";   file = "G4ABLA";             var = "G4ABLADATA";        sha256 = "1v97q28g1xqwnav0lwzwk7hc3b87yrmbvkgadf4bkwcbnm9b163n"; }
    { name = "G4ENSDFSTATE";       version = "2.2";   file = "G4ENSDFSTATE";       var = "G4ENSDFSTATEDATA";  sha256 = "19p0sq0rmyg48j9hddqy24dn99md7ddiyq09lyj381q7cbpjfznx"; }
  ];

  # The tarballs unpack to <name><version>/ (G4NDL4.5, PhotonEvaporation5.2,
  # ...) and that is the directory the environment variable has to name.
  dirOf = d: "${d.name}${d.version}";

in
stdenvNoCC.mkDerivation {
  pname = "geant4-data";
  version = "10.4.3";

  srcs = map (d: fetchurl {
    url = "${base}/${d.file}.${d.version}.tar.gz";
    inherit (d) sha256;
  }) datasets;

  sourceRoot = ".";

  dontBuild = true;
  dontFixup = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out/share/geant4-data
    cp -r -- * $out/share/geant4-data/

    # Fail loudly if a tarball ever unpacks somewhere other than the directory
    # the environment variable is about to name: the run-time symptom is a
    # physics process silently finding no data, which is far harder to trace
    # back here than a build failure.
    ${lib.concatMapStringsSep "\n" (d: ''
      test -d $out/share/geant4-data/${dirOf d} \
        || { echo "geant4-data: expected ${dirOf d}/ from ${d.file}.${d.version}.tar.gz" >&2; exit 1; }
    '') datasets}

    mkdir -p $out/nix-support
    {
    ${lib.concatMapStringsSep "\n" (d: ''
      echo "export ${d.var}=$out/share/geant4-data/${dirOf d}"'') datasets}
    } > $out/nix-support/setup-hook

    runHook postInstall
  '';

  passthru = {
    inherit datasets;
    # What a run-time environment has to export, for callers that build their
    # own environment rather than using the setup hook.
    variables = map (d: d.var) datasets;
  };

  meta = {
    description = "Physics datasets for Geant4 10.4";
    homepage = "https://geant4.web.cern.ch/support/download";
  };
}
