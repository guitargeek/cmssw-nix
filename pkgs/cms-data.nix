# cms-data repositories (github.com/cms-data/<Subsystem>-<Package>): the data
# files CMSSW distributes outside its own repository, as one tree,
# data/<Subsystem>/<Package>/data -> the repository.
#
# The tree is not used on its own: pkgs/cmssw-release.nix merges data trees
# into a release area (gen/release-with-data.sh), where scram puts them too.
# edm::FileInPath accepts files from the release area and from one data area
# (CMSSW_DATA_PATH), not from a list of them - and for a search path entry
# outside all three its walk up the directories never ends (it loops on
# "/") - so separate data packages on CMSSW_SEARCH_PATH do not compose.
{ lib, runCommand, name, repos }:

runCommand name { passthru = { inherit repos; }; } ''
  ${lib.concatMapStrings (r: ''
    mkdir -p $out/data/${r.path}
    ln -s ${r.src} $out/data/${r.path}/data
  '') repos}
''
