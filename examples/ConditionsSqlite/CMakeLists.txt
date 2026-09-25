cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME ConditionsSqlite)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(ConditionsSqliteTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(ConditionsSqliteTestPlugins PROPERTIES PREFIX "plugin")

target_link_libraries(ConditionsSqliteTestPlugins
  FWCoreFramework
  FWCoreServiceRegistry
  FWCoreUtilities
  # the payload and its EventSetup record, plus the service that stores it
  CondFormatsBeamSpotObjects
  CondFormatsDataRecord
  CondCoreDBOutputService
  ROOT::Core
  ${TBB_LIBS}
)
