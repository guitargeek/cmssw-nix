cmake_minimum_required(VERSION 3.22)
project(MuonGunDigiTest LANGUAGES CXX)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")

if(NOT DEFINED ENV{CMSSW_BASE})
  message(FATAL_ERROR "CMSSW_BASE is not set - run inside `nix develop`")
endif()
set(CMSSW_BASE $ENV{CMSSW_BASE})

if($ENV{CMSSW_VERSION} MATCHES "CMSSW_10_")
  set(CMAKE_CXX_STANDARD 17)
  # PoolDBOutputService renamed its write method between the two releases;
  # plugins/PixelLorentzAngleWriter.cc spells both through this macro.
  add_compile_definitions(CMSSW_10_6_ERA)
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

# The nanoAOD flat table over reco::Muon needs PhysicsTools/NanoAOD, which is
# in the 10_6 package set but not yet in the 20_1 one. Only
# python/muon_gun_nano_cfg.py uses it, and that config is 10_6-only for the
# same reason - so drop the plugin there rather than the whole example.
if(NOT $ENV{CMSSW_VERSION} MATCHES "CMSSW_10_")
  list(REMOVE_ITEM PLUGIN_FILES ${CMAKE_CURRENT_SOURCE_DIR}/plugins/RecoMuonFlatTableProducer.cc)
endif()

# The converse: PixelDetVOffWriter exists only because the 20_1
# SiPixelQualityESProducer consumes SiPixelDetVOffRcd unconditionally
# (see the file header). The 10_6 producer does not, so there is nothing
# for it to do there - and it uses PoolDBOutputService::writeOneIOV,
# which that era does not have.
if($ENV{CMSSW_VERSION} MATCHES "CMSSW_10_")
  list(REMOVE_ITEM PLUGIN_FILES ${CMAKE_CURRENT_SOURCE_DIR}/plugins/PixelDetVOffWriter.cc)
endif()
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
  # the empty HV-off map (plugins/PixelDetVOffWriter.cc, 20_1 only)
  CondFormatsSiStripObjects
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
  # the calorimeter energy response (plugins/CaloEnergyResponse.cc)
  DataFormatsEcalRecHit
  DataFormatsHcalRecHit
  DataFormatsEcalDetId
  DataFormatsHcalDetId
  SimDataFormatsCaloHit
  # nominal preshower conditions (plugins/PreshowerTrivialConditions.cc)
  CondFormatsESObjects
  CondFormatsDataRecord
  ROOT::Core
  ${TBB_LIBS}
)
