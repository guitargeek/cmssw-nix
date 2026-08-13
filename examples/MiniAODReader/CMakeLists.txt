cmake_minimum_required(VERSION 3.22)
project(MiniAODReader LANGUAGES CXX)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")

# Find the CMSSW install: headers under $CMSSW_BASE/src, libraries under
# $CMSSW_BASE/lib. In the nix devShell, CMSSW_BASE is set automatically.
if(NOT DEFINED ENV{CMSSW_BASE})
  message(FATAL_ERROR "CMSSW_BASE is not set - run inside `nix develop`")
endif()
set(CMSSW_BASE $ENV{CMSSW_BASE})

# Match the C++ standard CMSSW was built with (C++20 for modern releases,
# C++17 for the 10_6 era).
if($ENV{CMSSW_VERSION} MATCHES "CMSSW_10_")
  set(CMAKE_CXX_STANDARD 17)
else()
  set(CMAKE_CXX_STANDARD 20)
endif()
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(${CMSSW_BASE}/src)
link_directories(${CMSSW_BASE}/lib)

find_package(ROOT REQUIRED)
find_package(Boost REQUIRED)
# oneTBB ships a cmake config; classic TBB 2020 (10_6 era) does not.
find_package(TBB QUIET)
if(TBB_FOUND)
  set(TBB_LIBS TBB::tbb)
else()
  find_library(TBB_LIBS NAMES tbb REQUIRED)
endif()

# Add the plugin library as a target and make sure the name of the .so file
# starts with "plugin", as it would with scram.
file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(MiniAODReaderPlugins SHARED ${PLUGIN_FILES})
set_target_properties(MiniAODReaderPlugins PROPERTIES PREFIX "plugin")

# The CMSSW packages that we need to link against
target_link_libraries(MiniAODReaderPlugins
  FWCoreFramework
  FWCoreUtilities
  DataFormatsCommon
  DataFormatsPatCandidates
  DataFormatsMuonReco
  ROOT::Core ROOT::GenVector
  ${TBB_LIBS}
)
