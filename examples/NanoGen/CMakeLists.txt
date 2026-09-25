cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME NanoGen)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(NanoGenTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(NanoGenTestPlugins PROPERTIES PREFIX "plugin")

target_link_libraries(NanoGenTestPlugins
  FWCoreFramework
  FWCoreUtilities
  DataFormatsCandidate
  DataFormatsHepMCCandidate
  ROOT::Core
  ROOT::Physics
  ${TBB_LIBS}
)
