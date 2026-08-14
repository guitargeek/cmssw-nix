// Toy muon digi producer + local-reco checker: put straight-track-like digis
// into one DT chamber (4 hits in the phi superlayers SL1 and SL3 each), one
// CSC chamber (strip + wire digis on 4 layers) and one RPC roll, and let the
// standard rec-hit and segment producers run on them.

#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/Utilities/interface/Exception.h"

#include "DataFormats/DTDigi/interface/DTDigiCollection.h"
#include "DataFormats/CSCDigi/interface/CSCStripDigiCollection.h"
#include "DataFormats/CSCDigi/interface/CSCWireDigiCollection.h"
#include "DataFormats/RPCDigi/interface/RPCDigiCollection.h"
#include "DataFormats/MuonDetId/interface/DTLayerId.h"
#include "DataFormats/MuonDetId/interface/CSCDetId.h"
#include "DataFormats/MuonDetId/interface/RPCDetId.h"
#include "DataFormats/DTRecHit/interface/DTRecHitCollection.h"
#include "DataFormats/DTRecHit/interface/DTRecSegment4DCollection.h"
#include "DataFormats/CSCRecHit/interface/CSCRecHit2DCollection.h"
#include "DataFormats/CSCRecHit/interface/CSCSegmentCollection.h"
#include "DataFormats/RPCRecHit/interface/RPCRecHitCollection.h"
#include "FWCore/Framework/interface/ESHandle.h"
#include "Geometry/DTGeometry/interface/DTGeometry.h"
#include "Geometry/CSCGeometry/interface/CSCGeometry.h"
#include "Geometry/RPCGeometry/interface/RPCGeometry.h"
#include "Geometry/Records/interface/MuonGeometryRecord.h"

class ToyMuonDigiProducer : public edm::stream::EDProducer<> {
public:
  explicit ToyMuonDigiProducer(const edm::ParameterSet&) {
    produces<DTDigiCollection>();
    produces<CSCStripDigiCollection>("MuonCSCStripDigi");
    produces<CSCWireDigiCollection>("MuonCSCWireDigi");
    produces<RPCDigiCollection>();
  }

  void produce(edm::Event& event, const edm::EventSetup& setup) override {
    edm::ESHandle<DTGeometry> dtGeom;
    edm::ESHandle<CSCGeometry> cscGeom;
    edm::ESHandle<RPCGeometry> rpcGeom;
    setup.get<MuonGeometryRecord>().get(dtGeom);
    setup.get<MuonGeometryRecord>().get(cscGeom);
    setup.get<MuonGeometryRecord>().get(rpcGeom);
    edm::LogPrint("ToyMuonDigiProducer")
        << "geometry: " << dtGeom->chambers().size() << " DT chambers, "
        << cscGeom->chambers().size() << " CSC chambers, "
        << rpcGeom->rolls().size() << " RPC rolls";

    // DT: one digi in each of the 4 layers of the two phi superlayers of
    // chamber wheel 0, station 1, sector 1. TDC counts ~ (tTrig 500 ns +
    // drift ~200 ns) * 32/25
    auto dtDigis = std::make_unique<DTDigiCollection>();
    for (int sl : {1, 3})
      for (int layer = 1; layer <= 4; ++layer) {
        const DTLayerId layerId(0, 1, 1, sl, layer);
        DTDigi digi(10, 896 + 10 * layer, 0);
        dtDigis->insertDigi(layerId, digi);
      }

    // CSC: strip + wire digis on the 4 central layers of chamber ME1/1,
    // endcap 1, chamber 1: a pulse over 8 strip ADC samples (pedestal ~600)
    // and a wire digi in the matching wire group
    auto cscStripDigis = std::make_unique<CSCStripDigiCollection>();
    auto cscWireDigis = std::make_unique<CSCWireDigiCollection>();
    for (int layer = 2; layer <= 5; ++layer) {
      const CSCDetId id(1, 1, 1, 1, layer);
      const std::vector<int> adc = {600, 600, 810, 1000, 900, 750, 660, 620};
      cscStripDigis->insertDigi(id, CSCStripDigi(32, adc));
      // neighbouring strips with smaller pulses so the Gatti fit has a cluster
      const std::vector<int> adcSide = {600, 600, 705, 800, 750, 675, 630, 610};
      cscStripDigis->insertDigi(id, CSCStripDigi(31, adcSide));
      cscStripDigis->insertDigi(id, CSCStripDigi(33, adcSide));
      CSCWireDigi wireDigi(20, 6);
      cscWireDigis->insertDigi(id, wireDigi);
    }

    // RPC: two adjacent strips in the first barrel roll of the geometry
    // with enough strips
    auto rpcDigis = std::make_unique<RPCDigiCollection>();
    RPCDetId rpcId;
    for (const auto* roll : rpcGeom->rolls())
      if (roll->id().region() == 0 && roll->nstrips() >= 45) {
        rpcId = roll->id();
        break;
      }
    rpcDigis->insertDigi(rpcId, RPCDigi(40, 0));
    rpcDigis->insertDigi(rpcId, RPCDigi(41, 0));

    edm::LogPrint("ToyMuonDigiProducer")
        << "toy digis: 8 DT (Wh0/St1/Sec1 SL1+SL3), " << 12
        << " CSC strip + 4 wire (ME1/1), 2 RPC strips in " << rpcId;

    event.put(std::move(dtDigis));
    event.put(std::move(cscStripDigis), "MuonCSCStripDigi");
    event.put(std::move(cscWireDigis), "MuonCSCWireDigi");
    event.put(std::move(rpcDigis));
  }
};

class MuonLocalRecoChecker : public edm::one::EDAnalyzer<> {
public:
  explicit MuonLocalRecoChecker(const edm::ParameterSet& conf)
      : dtHitsToken_(consumes<DTRecHitCollection>(conf.getParameter<edm::InputTag>("dtRecHits"))),
        dtSegsToken_(consumes<DTRecSegment4DCollection>(conf.getParameter<edm::InputTag>("dtSegments"))),
        cscHitsToken_(consumes<CSCRecHit2DCollection>(conf.getParameter<edm::InputTag>("cscRecHits"))),
        cscSegsToken_(consumes<CSCSegmentCollection>(conf.getParameter<edm::InputTag>("cscSegments"))),
        rpcHitsToken_(consumes<RPCRecHitCollection>(conf.getParameter<edm::InputTag>("rpcRecHits"))) {}

  void analyze(const edm::Event& event, const edm::EventSetup& setup) override {
    edm::ESHandle<DTGeometry> dtGeom;
    edm::ESHandle<CSCGeometry> cscGeom;
    edm::ESHandle<RPCGeometry> rpcGeom;
    setup.get<MuonGeometryRecord>().get(dtGeom);
    setup.get<MuonGeometryRecord>().get(cscGeom);
    setup.get<MuonGeometryRecord>().get(rpcGeom);
    edm::LogPrint("MuonLocalRecoChecker")
        << "geometry: " << dtGeom->chambers().size() << " DT chambers, "
        << cscGeom->chambers().size() << " CSC chambers, "
        << rpcGeom->rolls().size() << " RPC rolls";

    const auto& dtHits = event.get(dtHitsToken_);
    const auto& dtSegs = event.get(dtSegsToken_);
    const auto& cscHits = event.get(cscHitsToken_);
    const auto& cscSegs = event.get(cscSegsToken_);
    const auto& rpcHits = event.get(rpcHitsToken_);

    edm::LogPrint("MuonLocalRecoChecker")
        << "DT rec hits: " << dtHits.size() << ", DT 4D segments: " << dtSegs.size()
        << ", CSC rec hits: " << cscHits.size() << ", CSC segments: " << cscSegs.size()
        << ", RPC rec hits: " << rpcHits.size();

    for (const auto& seg : dtSegs)
      edm::LogPrint("MuonLocalRecoChecker")
          << "DT 4D segment in " << seg.chamberId()
          << ": local pos (" << seg.localPosition().x() << ", " << seg.localPosition().y()
          << "), dir (" << seg.localDirection().x() << ", " << seg.localDirection().y() << ")";
    for (const auto& seg : cscSegs)
      edm::LogPrint("MuonLocalRecoChecker")
          << "CSC segment in " << seg.cscDetId()
          << ": " << seg.nRecHits() << " hits, local pos ("
          << seg.localPosition().x() << ", " << seg.localPosition().y() << ")";
    for (const auto& hit : rpcHits)
      edm::LogPrint("MuonLocalRecoChecker")
          << "RPC rec hit in " << hit.rpcId() << ": local x = " << hit.localPosition().x();

    if (dtHits.size() != 8 || dtSegs.size() != 1)
      throw cms::Exception("MuonLocalRecoChecker")
          << "expected 8 DT rec hits and one 4D segment";
    if (cscHits.size() != 4 || cscSegs.size() != 1)
      throw cms::Exception("MuonLocalRecoChecker")
          << "expected 4 CSC rec hits and one segment";
    if (rpcHits.size() != 1)
      throw cms::Exception("MuonLocalRecoChecker") << "expected one RPC rec hit";
  }

private:
  edm::EDGetTokenT<DTRecHitCollection> dtHitsToken_;
  edm::EDGetTokenT<DTRecSegment4DCollection> dtSegsToken_;
  edm::EDGetTokenT<CSCRecHit2DCollection> cscHitsToken_;
  edm::EDGetTokenT<CSCSegmentCollection> cscSegsToken_;
  edm::EDGetTokenT<RPCRecHitCollection> rpcHitsToken_;
};

#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(ToyMuonDigiProducer);
DEFINE_FWK_MODULE(MuonLocalRecoChecker);
