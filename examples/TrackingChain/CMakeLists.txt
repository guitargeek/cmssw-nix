cmake_minimum_required(VERSION 3.22)
project(TrackingChain LANGUAGES CXX)

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

# PixelLorentzAngleWriter exists for the 20_1 configuration, which has no
# usable SiPixelFakeLorentzAngleESSource (see the file's header). It is the
# same writer examples/TrackerLocalReco carries, for the same reason, and it
# uses PoolDBOutputService::writeOneIOV, which 10_6 does not have - so leave
# it out there, where the fake source works and the writer is not needed.
if($ENV{CMSSW_VERSION} MATCHES "CMSSW_10_")
  list(REMOVE_ITEM PLUGIN_FILES ${CMAKE_CURRENT_SOURCE_DIR}/plugins/PixelLorentzAngleWriter.cc)
endif()
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
