cmake_minimum_required(VERSION 3.22)
project(MuonGunDigiTest LANGUAGES CXX)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")

if(NOT DEFINED ENV{CMSSW_BASE})
  message(FATAL_ERROR "CMSSW_BASE is not set - run inside `nix develop`")
endif()
set(CMSSW_BASE $ENV{CMSSW_BASE})

if($ENV{CMSSW_VERSION} MATCHES "CMSSW_10_")
  set(CMAKE_CXX_STANDARD 17)
else()
  set(CMAKE_CXX_STANDARD 20)
endif()
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(${CMSSW_BASE}/src)
link_directories(${CMSSW_BASE}/lib)

find_package(ROOT REQUIRED)
find_package(Boost REQUIRED)
find_library(TBB_LIBS NAMES tbb REQUIRED)

file(GLOB PLUGIN_FILES plugins/*.cc)
add_library(MuonGunDigiTestPlugins SHARED ${PLUGIN_FILES})
set_target_properties(MuonGunDigiTestPlugins PROPERTIES PREFIX "plugin")

# The digi data formats and the SimHits they came from - the analyzer compares
# the two. It links neither Geant4 nor the digitisers themselves.
target_link_libraries(MuonGunDigiTestPlugins
  FWCoreFramework
  FWCoreServiceRegistry
  CondFormatsSiPixelObjects
  GeometryTrackerGeometryBuilder
  DataFormatsSiPixelDetId
  CondCoreDBOutputService
  FWCoreMessageLogger
  FWCoreUtilities
  DataFormatsCommon
  DataFormatsSiPixelDigi
  DataFormatsSiStripDigi
  DataFormatsDetId
  DataFormatsTrackerCommon
  DataFormatsTrackerRecHit2D
  DataFormatsGeometryVector
  SimDataFormatsTrackingHit
  SimDataFormatsTrack
  DataFormatsTrackReco
  DataFormatsVertexReco
  SimDataFormatsVertex
  # the nanoAOD flat table over reco::Muon (plugins/RecoMuonFlatTableProducer.cc)
  DataFormatsMuonReco
  DataFormatsNanoAOD
  CommonToolsUtils
  # the empty CSC/RPC collections (plugins/EmptyMuonCollectionProducers.cc)
  DataFormatsCSCRecHit
  DataFormatsRPCRecHit
  ROOT::Core
  ${TBB_LIBS}
)
