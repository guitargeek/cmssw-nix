// Empty CSC segment and RPC rec-hit collections.
//
// The gun fires into |eta| < 0.8, which is the barrel: no muon in this
// example ever reaches a CSC chamber, no CSC or RPC digi is simulated, and no
// CSC or RPC local reconstruction runs. MuonIdProducer nevertheless asks for
// both collections for every muon it builds - the timing filler runs
// unconditionally and hands each muon to MuonSegmentMatcher, which fetches
// the segments before it has any way of knowing that the muon is in the
// barrel and that the answer will be empty.
//
// A missing product is an exception, an empty one is not, so these producers
// exist to make those fetches succeed with the honest answer. They are not
// stubs standing in for reconstruction that should be happening: with no CSC
// or RPC digis in the file, an empty collection is exactly what the local
// reconstruction would produce if it were run.
#include "FWCore/Framework/interface/global/EDProducer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"

#include "DataFormats/CSCRecHit/interface/CSCSegmentCollection.h"
#include "DataFormats/RPCRecHit/interface/RPCRecHitCollection.h"

namespace {
  template <typename T>
  class EmptyCollectionProducer : public edm::global::EDProducer<> {
  public:
    explicit EmptyCollectionProducer(const edm::ParameterSet&) { this->template produces<T>(); }

    void produce(edm::StreamID, edm::Event& event, const edm::EventSetup&) const override {
      event.put(std::make_unique<T>());
    }
  };
}  // namespace

typedef EmptyCollectionProducer<CSCSegmentCollection> EmptyCSCSegmentProducer;
typedef EmptyCollectionProducer<RPCRecHitCollection> EmptyRPCRecHitProducer;

DEFINE_FWK_MODULE(EmptyCSCSegmentProducer);
DEFINE_FWK_MODULE(EmptyRPCRecHitProducer);
