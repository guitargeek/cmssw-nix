cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME MuonChain)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(MuonChainTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(MuonChainTestPlugins PROPERTIES PREFIX "plugin")

target_link_libraries(MuonChainTestPlugins
  FWCoreFramework
  FWCoreUtilities
  DataFormatsDTDigi
  DataFormatsMuonDetId
  DataFormatsTrackReco
  DataFormatsTrajectorySeed
  GeometryDTGeometry
  GeometryRecords
  MagneticFieldEngine
  MagneticFieldRecords
  ROOT::Core
  ${TBB_LIBS}
)
