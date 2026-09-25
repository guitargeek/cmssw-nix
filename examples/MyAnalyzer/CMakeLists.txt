cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME MyAnalyzer)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(MyAnalyzerTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(MyAnalyzerTestPlugins PROPERTIES PREFIX "plugin")

# The CMSSW packages that we need to link against
target_link_libraries(MyAnalyzerTestPlugins
  FWCoreFramework
  FWCoreUtilities
  DataFormatsCommon
  DataFormatsEgammaCandidates
  ROOT::Core ROOT::GenVector
  ${TBB_LIBS}
)
