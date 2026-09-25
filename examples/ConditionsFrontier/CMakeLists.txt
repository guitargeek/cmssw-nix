cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME ConditionsFrontier)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(ConditionsFrontierTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(ConditionsFrontierTestPlugins PROPERTIES PREFIX "plugin")

target_link_libraries(ConditionsFrontierTestPlugins
  FWCoreFramework
  FWCoreServiceRegistry
  FWCoreUtilities
  # the CondCore session API, which is what pulls in CORAL
  CondCoreCondDB
  ROOT::Core
  ${TBB_LIBS}
)
