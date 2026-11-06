# Geant4 is built multi-threaded, and its CMake then compiles the whole
# toolkit with -ftls-model=initial-exec. libG4processes_hadronic.so ends up
# with a 1.2 MB PT_TLS segment that has to come out of the *static* TLS
# surplus - and glibc's default surplus is 512 bytes. Any CMSSW library that
# pulls in geant4 (78 of the 627 in the 20_1 build) therefore fails to
# dlopen with "cannot allocate memory in static TLS block", even though it
# links fine. cmsRun only survives because it dlopens a subset.
#
# 2 MB of surplus covers it. The cost is 2 MB of address space per thread,
# which is nothing next to a CMSSW job. The alternative - rebuilding geant4
# with -DGEANT4_BUILD_TLS_MODEL=global-dynamic - is cleaner in principle but
# would mean nobody can ever substitute the stock geant4 (or anything built
# on top of it) from the binary cache again.
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
