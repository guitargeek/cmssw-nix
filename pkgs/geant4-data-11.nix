# The Geant4 11 physics datasets, for the 20_1 simulation.
#
# Unlike pkgs/geant4-data.nix - which fetches the 10.4 tarballs itself,
# because nixpkgs has no Geant4 10 - nixpkgs already packages every 11.x
# dataset as `geant4.data.<name>`. This derivation only collects them into
# one setup hook.
#
# It has to, rather than the shells simply depending on `geant4.data.*`
# directly, because each nixpkgs dataset ships its export wrapped in a shell
# function appended to `postHooks`. That is a build-time stdenv mechanism:
# genericBuild calls it, an interactive `nix develop` never does, so the
# variables would silently be unset in exactly the environment the examples
# run in. The export lines are lifted out here instead.
#
# The variable names and dataset versions are read out of those hooks at
# build time rather than restated, so a nixpkgs bump to a new dataset version
# cannot leave a stale path behind. Getting one of these wrong does not fail
# the build; it fails at run time, usually as a physics process quietly
# finding no data.
{ lib, stdenvNoCC, geant4 }:

let
  datasets = lib.filter lib.isDerivation (lib.attrValues geant4.data);
in
stdenvNoCC.mkDerivation {
  pname = "geant4-data";
  version = geant4.version;

  dontUnpack = true;
  dontBuild = true;
  dontFixup = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out/nix-support
    for dataset in ${lib.concatStringsSep " " (map toString datasets)}; do
      hook=$dataset/nix-support/setup-hook
      test -f "$hook" || { echo "geant4-data: no setup hook in $dataset" >&2; exit 1; }
      grep -oE 'export [A-Z0-9_]+="[^"]*"' "$hook" >> $out/nix-support/setup-hook \
        || { echo "geant4-data: no export line in $hook" >&2; exit 1; }
    done
    # One line per dataset, or something upstream changed shape
    test "$(wc -l < $out/nix-support/setup-hook)" -eq ${toString (builtins.length datasets)} \
      || { echo "geant4-data: expected ${toString (builtins.length datasets)} exports, got $(wc -l < $out/nix-support/setup-hook)" >&2; exit 1; }
    runHook postInstall
  '';

  meta = {
    description = "Physics datasets for Geant4 ${geant4.version}, as one setup hook";
    homepage = "https://geant4.web.cern.ch/support/download";
  };
}
