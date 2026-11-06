# The 10_6 release's Geant4 10.4 (pkgs/geant4.nix) is built multi-threaded
# with Geant4's default initial-exec TLS model: libG4processes_hadronic.so
# ends up with a 1.2 MB PT_TLS segment that has to come out of the *static*
# TLS surplus - and glibc's default surplus is 512 bytes. Any library that
# pulls in Geant4 therefore fails to dlopen with "cannot allocate memory in
# static TLS block", even though it links fine. 2 MB of surplus covers it,
# at 2 MB of address space per thread. (The 20_1 Geant4 is built with the
# global-dynamic model and needs none; the hook is shared by both.)
#
# (glibc only: Mach-O allocates thread-locals on demand, so macOS has no
# static TLS block to run out of.)
case "$OSTYPE" in
linux*)
    _cmssw_tls=glibc.rtld.optional_static_tls=2097152
    export GLIBC_TUNABLES=${GLIBC_TUNABLES:+$GLIBC_TUNABLES:}$_cmssw_tls
    unset _cmssw_tls
    ;;
esac

export CMSSW_BASE=@out@
export CMSSW_RELEASE_BASE=@out@
export CMSSW_VERSION=@version@
export CMSSW_SEARCH_PATH=@out@/src
# modern releases look up the site config via SITECONFIG_PATH, 10_6-era ones
# via $CMS_PATH/SITECONF/local/...
if [ -d @out@/siteconf ]; then
    export SITECONFIG_PATH=@out@/siteconf
fi
if [ -d @out@/SITECONF ]; then
    export CMS_PATH=@out@
fi
addToSearchPath PATH @out@/bin
addToSearchPath LD_LIBRARY_PATH @out@/lib
# where DD4hep looks for the .components files of the release's DD4hep
# plugins: DD4HEP_LIBRARY_PATH on macOS (pkgs/dd4hep.nix), LD_LIBRARY_PATH
# on Linux
if [ -d @out@/dd4hep ]; then
    addToSearchPath DD4HEP_LIBRARY_PATH @out@/dd4hep
    addToSearchPath LD_LIBRARY_PATH @out@/dd4hep
fi
addToSearchPath PYTHONPATH @out@/python
addToSearchPath PYTHONPATH @out@/lib
addToSearchPath ROOT_INCLUDE_PATH @out@/src
