cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME MuonGunSim)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(MuonGunSimTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(MuonGunSimTestPlugins PROPERTIES PREFIX "plugin")

# Only the SimHit data formats: the analyzer reads what the simulation wrote,
# it does not link Geant4 itself.
target_link_libraries(MuonGunSimTestPlugins
  FWCoreFramework
  FWCoreMessageLogger
  FWCoreUtilities
  SimDataFormatsTrackingHit
  SimDataFormatsTrack
  SimDataFormatsVertex
  ROOT::Core
  ${TBB_LIBS}
)
