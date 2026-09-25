cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME CaloLocalReco)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(CaloLocalRecoTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(CaloLocalRecoTestPlugins PROPERTIES PREFIX "plugin")

target_link_libraries(CaloLocalRecoTestPlugins
  FWCoreFramework
  FWCoreUtilities
  DataFormatsCommon
  DataFormatsDetId
  DataFormatsEcalDetId
  DataFormatsEcalDigi
  DataFormatsEcalRecHit
  DataFormatsHcalDetId
  DataFormatsHcalDigi
  DataFormatsHcalRecHit
  DataFormatsCaloTowers
  GeometryCaloGeometry
  GeometryRecords
  ROOT::Core
  ${TBB_LIBS}
)
