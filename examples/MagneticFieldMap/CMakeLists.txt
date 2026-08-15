cmake_minimum_required(VERSION 3.22)
project(MagneticFieldMapTest LANGUAGES CXX)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")

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
find_library(TBB_LIBS NAMES tbb REQUIRED)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(MagneticFieldMapTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(MagneticFieldMapTestPlugins PROPERTIES PREFIX "plugin")

target_link_libraries(MagneticFieldMapTestPlugins
  FWCoreFramework
  FWCoreUtilities
  MagneticFieldEngine
  # the IdealMagneticFieldRecord typelookup symbol lives here; without it the
  # plugin library fails to dlopen and edmPluginRefresh silently registers
  # nothing (an empty .edmplugincache, not an error)
  MagneticFieldRecords
  ROOT::Core
  ${TBB_LIBS}
)
