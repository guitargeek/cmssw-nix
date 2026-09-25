cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME MagneticFieldMap)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(MagneticFieldMapTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(MagneticFieldMapTestPlugins PROPERTIES PREFIX "plugin")

target_link_libraries(MagneticFieldMapTestPlugins
  FWCoreFramework
  FWCoreUtilities
  MagneticFieldEngine
  # the IdealMagneticFieldRecord typelookup symbol lives here; without it the
  # plugin library fails to dlopen and edmPluginRefresh silently registers
  # nothing (an empty .edmplugincache, not an error)
  MagneticFieldRecords
  ROOT::Core
  ${TBB_LIBS}
)
