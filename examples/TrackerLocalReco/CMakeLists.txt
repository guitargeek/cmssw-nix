cmake_minimum_required(VERSION 3.22)
project(TrackerLocalRecoTest LANGUAGES CXX)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")

if(NOT DEFINED ENV{CMSSW_BASE})
  message(FATAL_ERROR "CMSSW_BASE is not set - run inside `nix develop`")
endif()
set(CMSSW_BASE $ENV{CMSSW_BASE})

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(${CMSSW_BASE}/src)
link_directories(${CMSSW_BASE}/lib)

find_package(ROOT REQUIRED)
find_package(Boost REQUIRED)
find_library(TBB_LIBS NAMES tbb REQUIRED)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(TrackerLocalRecoTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(TrackerLocalRecoTestPlugins PROPERTIES PREFIX "plugin")

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
  GeometryCommonDetUnit
  GeometryRecords
  ROOT::Core
  ${TBB_LIBS}
)
