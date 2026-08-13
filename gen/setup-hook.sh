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
addToSearchPath PYTHONPATH @out@/python
addToSearchPath PYTHONPATH @out@/lib
addToSearchPath ROOT_INCLUDE_PATH @out@/src
