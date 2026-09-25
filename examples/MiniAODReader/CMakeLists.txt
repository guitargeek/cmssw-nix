cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME MiniAODReader)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(MiniAODReaderTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(MiniAODReaderTestPlugins PROPERTIES PREFIX "plugin")

# The CMSSW packages that we need to link against
target_link_libraries(MiniAODReaderTestPlugins
  FWCoreFramework
  FWCoreUtilities
  DataFormatsCommon
  DataFormatsPatCandidates
  DataFormatsMuonReco
  ROOT::Core ROOT::GenVector
  ${TBB_LIBS}
)
