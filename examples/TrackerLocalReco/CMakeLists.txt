cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME TrackerLocalReco)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
list(APPEND PLUGIN_FILES ${CMAKE_CURRENT_LIST_DIR}/../common/plugins/PixelLorentzAngleWriter.cc)

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
