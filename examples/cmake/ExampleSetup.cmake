# Shared CMake preamble for the examples: find the CMSSW install
# ($CMSSW_BASE), match its C++ standard, point at its headers and
# libraries, and find the externals every example links. The example
# declares EXAMPLE_NAME, includes this file, then declares and links its
# plugin library:
#
#   set(EXAMPLE_NAME MyExample)
#   include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)
#
#   file(GLOB PLUGIN_FILES plugins/*.cc)
#   add_library(MyExampleTestPlugins SHARED ${PLUGIN_FILES})
#   set_target_properties(MyExampleTestPlugins PROPERTIES PREFIX "plugin")
#   target_link_libraries(MyExampleTestPlugins FWCoreFramework ...)
#
# Compile against the nix toolchain's SDK, never the host's: see the same
# block in gen/CMakeLists.txt for why. FORCE, because by the time this file
# is read the platform has been set up already, host SDK included: the
# examples' CMakeLists.txt have no project() call of their own, so CMake runs
# an implicit one before anything else. The sysroot is only read when the
# build commands are generated, so setting it here still takes.
if(APPLE)
  set(CMAKE_OSX_SYSROOT "$ENV{SDKROOT}" CACHE PATH "macOS SDK (from SDKROOT, empty for the toolchain default)" FORCE)
endif()
project(${EXAMPLE_NAME}Test LANGUAGES CXX)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")

# Plugins name only the CMSSW libraries they use directly and leave the rest
# of their symbols to be resolved when cmsRun loads them, as ELF allows. The
# macOS linker wants every symbol of a library resolved at link time; let it
# defer them the same way the release itself does (gen/CMakeLists.txt).
if(APPLE)
  set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -undefined dynamic_lookup")
endif()

if(NOT DEFINED ENV{CMSSW_BASE})
  message(FATAL_ERROR "CMSSW_BASE is not set - run inside `nix develop`")
endif()
set(CMSSW_BASE $ENV{CMSSW_BASE})

# Match the C++ standard CMSSW was built with (C++20 for modern releases,
# C++17 for the 10_6 era). CMSSW_10_6_ERA lets plugin sources spell the
# two eras' APIs apart where they differ (e.g. PoolDBOutputService::write
# vs writeOneIOV, in common/plugins/PixelLorentzAngleWriter.cc).
if($ENV{CMSSW_VERSION} MATCHES "CMSSW_10_")
  set(CMAKE_CXX_STANDARD 17)
  add_compile_definitions(CMSSW_10_6_ERA)
else()
  set(CMAKE_CXX_STANDARD 20)
endif()
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(${CMSSW_BASE}/src)
link_directories(${CMSSW_BASE}/lib)

find_package(ROOT REQUIRED)
find_package(Boost REQUIRED)
# oneTBB ships a cmake config; classic TBB 2020 (10_6 era) does not.
find_package(TBB QUIET)
if(TBB_FOUND)
  set(TBB_LIBS TBB::tbb)
else()
  find_library(TBB_LIBS NAMES tbb REQUIRED)
endif()
