cmake_minimum_required(VERSION 3.22)
set(EXAMPLE_NAME MuonGunDigi)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/ExampleSetup.cmake)

file(GLOB PLUGIN_FILES plugins/*.cc)
list(APPEND PLUGIN_FILES ${CMAKE_CURRENT_LIST_DIR}/../common/plugins/PixelLorentzAngleWriter.cc)

# PixelDetVOffWriter exists only because the 20_1
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
