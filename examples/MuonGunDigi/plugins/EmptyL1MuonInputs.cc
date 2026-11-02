// Empty inputs for the parts of the L1 muon trigger this example cannot feed.
//
// The global muon trigger (uGMT) merges three track finders - barrel (BMTF),
// overlap (OMTF, 0.83 < |eta| < 1.24) and endcap (EMTF) - and reads calorimeter
// tower sums for its isolation. TwinMux, in front of the barrel track
// finder, combines the DT trigger primitives with RPC hits. All of these
// inputs are required: the producers dereference their handles without
// checking them, so a missing product is an exception.
//
// The gun fires into |eta| < 0.8, the barrel, and the example simulates no RPC
// digis, so an empty collection is the honest answer for each of them, the
// same reasoning as plugins/EmptyMuonCollectionProducers.cc: with no muon in
// their acceptance, the overlap and endcap track finders would find nothing.
// The calorimeter tower sums are only used for the isolation bits, which
// the test does not look at.
#include "DataFormats/L1TMuon/interface/MuonCaloSum.h"
#include "DataFormats/L1TMuon/interface/MuonCaloSumFwd.h"
#include "DataFormats/L1TMuon/interface/RegionalMuonCand.h"
#include "DataFormats/RPCDigi/interface/RPCDigiCollection.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/global/EDProducer.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"

namespace {
  template <typename T>
  class EmptyL1Input : public edm::global::EDProducer<> {
  public:
    explicit EmptyL1Input(const edm::ParameterSet&) { this->template produces<T>(); }

    void produce(edm::StreamID, edm::Event& event, const edm::EventSetup&) const override {
      event.put(std::make_unique<T>());
    }
  };
}  // namespace

typedef EmptyL1Input<l1t::RegionalMuonCandBxCollection> EmptyRegionalMuonCandProducer;
typedef EmptyL1Input<l1t::MuonCaloSumBxCollection> EmptyMuonCaloSumProducer;
typedef EmptyL1Input<RPCDigiCollection> EmptyRPCDigiProducer;

DEFINE_FWK_MODULE(EmptyRegionalMuonCandProducer);
DEFINE_FWK_MODULE(EmptyMuonCaloSumProducer);
DEFINE_FWK_MODULE(EmptyRPCDigiProducer);
