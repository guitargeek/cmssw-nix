# A release as users get it: a build of CMSSW (pkgs/cmssw.nix) with the
# cms-data it reads merged into its release area (pkgs/cms-data.nix,
# gen/release-with-data.sh). Only links: a change to the data rebuilds this
# in seconds and leaves the build alone.
{ lib, runCommandCC, build, data ? [ ] }:

runCommandCC "cmssw-${build.version}" {
  # what the build propagates (on darwin, the deployment target its users
  # have to share; its setup hook needs a stdenv with a compiler, hence
  # runCommandCC), so that this package can stand in for it
  propagatedBuildInputs = build.propagatedBuildInputs or [ ];
  passthru = {
    inherit build data;
    inherit (build) version pythonEnv hardeningDisable;
  };
  inherit (build) meta;
} ''
  bash ${../gen/release-with-data.sh} ${build} $out ${lib.escapeShellArgs data}
''
