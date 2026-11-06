# cms-data repositories as one data area outside the release: what the
# standard Run 3 sequences read (examples/CmsDriverChain) is some 2 GB of
# trained models and weight files, which the release itself - and every
# build of it - does without.
#
# The layout is CMSSW's: data/<Subsystem>/<Package>/data/..., on the
# CMSSW_SEARCH_PATH after the release's src/. CMSSW_DATA_PATH names the
# directory above it, as on a CMS installation: edm::FileInPath walks up
# from the search path entry a file was found in until it meets one of
# CMSSW_BASE, CMSSW_RELEASE_BASE or CMSSW_DATA_PATH, and for an entry below
# none of them the walk never ends (it loops on "/").
#
# The setup hook appends to the release's CMSSW_SEARCH_PATH, which the
# release's own hook sets: list this package after the release.
{ lib, runCommand, name, repos }:

runCommand name { passthru = { inherit repos; }; } ''
  ${lib.concatMapStrings (r: ''
    mkdir -p $out/data/${r.path}
    ln -s ${r.src} $out/data/${r.path}/data
  '') repos}
  # (runCommand does not install a setupHook attribute)
  mkdir -p $out/nix-support
  cat > $out/nix-support/setup-hook <<EOF
  addToSearchPath CMSSW_SEARCH_PATH $out/data
  export CMSSW_DATA_PATH=$out
  EOF
''
