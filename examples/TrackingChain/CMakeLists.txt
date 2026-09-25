cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME TrackingChain)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
list(APPEND PLUGIN_FILES ${CMAKE_CURRENT_LIST_DIR}/../common/plugins/PixelLorentzAngleWriter.cc)

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
