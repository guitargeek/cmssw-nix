export CMSSW_BASE=@out@
export CMSSW_RELEASE_BASE=@out@
export CMSSW_VERSION=@version@
export CMSSW_SEARCH_PATH=@out@/src
export SITECONFIG_PATH=@out@/siteconf
addToSearchPath PATH @out@/bin
addToSearchPath LD_LIBRARY_PATH @out@/lib
addToSearchPath PYTHONPATH @out@/python
addToSearchPath PYTHONPATH @out@/lib
addToSearchPath ROOT_INCLUDE_PATH @out@/src
