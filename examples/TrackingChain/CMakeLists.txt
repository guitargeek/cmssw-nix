cmake_minimum_required(VERSION 3.22)
project(TrackingChain LANGUAGES CXX)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")

if(NOT DEFINED ENV{CMSSW_BASE})
  message(FATAL_ERROR "CMSSW_BASE is not set - run inside `nix develop`")
endif()
set(CMSSW_BASE $ENV{CMSSW_BASE})

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# PoolDBOutputService renamed its write method between the two releases;
# plugins/PixelLorentzAngleWriter.cc spells both through this macro.
if($ENV{CMSSW_VERSION} MATCHES "CMSSW_10_")
  add_compile_definitions(CMSSW_10_6_ERA)
endif()

include_directories(${CMSSW_BASE}/src)
link_directories(${CMSSW_BASE}/lib)

find_package(ROOT REQUIRED)
find_package(Boost REQUIRED)
find_library(TBB_LIBS NAMES tbb REQUIRED)

file(GLOB PLUGIN_FILES plugins/*.cc)

add_library(TrackingChainPlugins SHARED ${PLUGIN_FILES})
set_target_properties(TrackingChainPlugins PROPERTIES PREFIX "plugin")

# Geometry/CommonDetUnit was merged away after the 10_6 era; link it only
# where it exists.
find_library(GEOMETRY_COMMONDETUNIT NAMES GeometryCommonDetUnit
             PATHS ${CMSSW_BASE}/lib NO_DEFAULT_PATH)
if(NOT GEOMETRY_COMMONDETUNIT)
  set(GEOMETRY_COMMONDETUNIT "")
endif()

target_link_libraries(TrackingChainPlugins
  FWCoreFramework
  FWCoreUtilities
  DataFormatsCommon
  DataFormatsDetId
  DataFormatsSiPixelDigi
  DataFormatsSiStripDigi
  DataFormatsTrackReco
  DataFormatsTrajectorySeed
  DataFormatsVertexReco
  DataFormatsGeometrySurface
  DataFormatsGeometryVector
  GeometryTrackerGeometryBuilder
  ${GEOMETRY_COMMONDETUNIT}
  GeometryCommonTopologies
  GeometryRecords
  # the pixel Lorentz angle writer (20_1 only, see above)
  CondFormatsSiPixelObjects
  CondCoreDBOutputService
  ROOT::Core ROOT::GenVector
  ${TBB_LIBS}
)
