cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME MuonLocalReco)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(MuonLocalRecoTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(MuonLocalRecoTestPlugins PROPERTIES PREFIX "plugin")

target_link_libraries(MuonLocalRecoTestPlugins
  FWCoreFramework
  FWCoreUtilities
  DataFormatsCommon
  DataFormatsMuonDetId
  DataFormatsDTDigi
  DataFormatsCSCDigi
  DataFormatsRPCDigi
  DataFormatsDTRecHit
  DataFormatsCSCRecHit
  DataFormatsRPCRecHit
  DataFormatsGeometrySurface
  GeometryDTGeometry
  GeometryCSCGeometry
  GeometryRPCGeometry
  GeometryRecords
  ROOT::Core
  ${TBB_LIBS}
)
