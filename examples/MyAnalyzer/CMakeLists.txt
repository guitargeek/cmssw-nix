cmake_minimum_required(VERSION 3.25)
project(MyAnalyzer LANGUAGES CXX)

# CMSSW is built with C++20
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")

# Find the CMSSW install: headers under $CMSSW_BASE/src, libraries under
# $CMSSW_BASE/lib. In the nix devShell, CMSSW_BASE is set automatically.
if(NOT DEFINED ENV{CMSSW_BASE})
  message(FATAL_ERROR "CMSSW_BASE is not set - run inside `nix develop`")
endif()
set(CMSSW_BASE $ENV{CMSSW_BASE})

include_directories(${CMSSW_BASE}/src)
link_directories(${CMSSW_BASE}/lib)

find_package(ROOT REQUIRED)
find_package(Boost REQUIRED)
find_package(TBB REQUIRED)

# Add the plugin library as a target and make sure the name of the .so file
# starts with "plugin", as it would with scram.
file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(MyAnalyzerPlugins SHARED ${PLUGIN_FILES})
set_target_properties(MyAnalyzerPlugins PROPERTIES PREFIX "plugin")

# The CMSSW packages that we need to link against
target_link_libraries(MyAnalyzerPlugins
  FWCoreFramework
  FWCoreUtilities
  DataFormatsCommon
  DataFormatsEgammaCandidates
  ROOT::Core ROOT::GenVector
  TBB::tbb
)
