cmake_minimum_required(VERSION 3.22)
project(TrackerLocalRecoTest LANGUAGES CXX)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")

if(NOT DEFINED ENV{CMSSW_BASE})
  message(FATAL_ERROR "CMSSW_BASE is not set - run inside `nix develop`")
endif()
set(CMSSW_BASE $ENV{CMSSW_BASE})

# Match the C++ standard CMSSW was built with (C++20 for modern releases,
# C++17 for the 10_6 era).
if($ENV{CMSSW_VERSION} MATCHES "CMSSW_10_")
  set(CMAKE_CXX_STANDARD 17)
  # PoolDBOutputService renamed its write method between the two releases;
  # plugins/PixelLorentzAngleWriter.cc spells both through this macro.
  add_compile_definitions(CMSSW_10_6_ERA)
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

add_library(TrackerLocalRecoTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(TrackerLocalRecoTestPlugins PROPERTIES PREFIX "plugin")

# Geometry/CommonDetUnit was merged away after the 10_6 era; link it only
# where it exists.
find_library(GEOMETRY_COMMONDETUNIT NAMES GeometryCommonDetUnit
             PATHS ${CMSSW_BASE}/lib NO_DEFAULT_PATH)
if(NOT GEOMETRY_COMMONDETUNIT)
  set(GEOMETRY_COMMONDETUNIT "")
endif()

target_link_libraries(TrackerLocalRecoTestPlugins
  FWCoreFramework
  FWCoreUtilities
  DataFormatsCommon
  DataFormatsDetId
  DataFormatsSiPixelDigi
  DataFormatsSiStripDigi
  DataFormatsSiPixelCluster
  DataFormatsSiStripCluster
  DataFormatsTrackerRecHit2D
  GeometryTrackerGeometryBuilder
  GeometryCommonTopologies
  ${GEOMETRY_COMMONDETUNIT}
  GeometryRecords
  FWCoreServiceRegistry
  CondFormatsSiPixelObjects
  CondCoreDBOutputService
  ROOT::Core
  ${TBB_LIBS}
)
