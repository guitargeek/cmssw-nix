// Toy tracker digi producer + local-reco checker, used to validate the
// tracker local reco chain (digis -> clusters -> rec hits) without real data:
// place a few adjacent digis on the first pixel and first strip module of the
// TrackerGeometry and let the standard clusterizers/CPEs run on them.

#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/ESHandle.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"

#include "DataFormats/Common/interface/DetSetVector.h"
#include "DataFormats/Common/interface/DetSetVectorNew.h"
#include "DataFormats/SiStripDigi/interface/SiStripDigi.h"
#include "DataFormats/SiPixelDigi/interface/PixelDigi.h"
#include "DataFormats/SiStripCluster/interface/SiStripCluster.h"
#include "DataFormats/SiPixelCluster/interface/SiPixelCluster.h"
#include "DataFormats/TrackerRecHit2D/interface/SiStripRecHit2DCollection.h"
#include "DataFormats/TrackerRecHit2D/interface/SiPixelRecHitCollection.h"

#include "Geometry/TrackerGeometryBuilder/interface/TrackerGeometry.h"
#include "Geometry/Records/interface/TrackerDigiGeometryRecord.h"
#include "Geometry/CommonDetUnit/interface/GeomDet.h"
#include "DataFormats/DetId/interface/DetId.h"
#include "DataFormats/SiStripDetId/interface/StripSubdetector.h"
#include "DataFormats/SiPixelDetId/interface/PixelSubdetector.h"

class ToyTrackerDigiProducer : public edm::stream::EDProducer<> {
public:
  explicit ToyTrackerDigiProducer(const edm::ParameterSet&) {
    produces<edm::DetSetVector<SiStripDigi>>();
    produces<edm::DetSetVector<PixelDigi>>();
  }

  void produce(edm::Event& event, const edm::EventSetup& setup) override {
    edm::ESHandle<TrackerGeometry> geom;
    setup.get<TrackerDigiGeometryRecord>().get(geom);

    DetId pixelDet, stripDet;
    for (const auto* du : geom->detUnits()) {
      DetId id = du->geographicalId();
      if (pixelDet.rawId() == 0 && id.subdetId() == PixelSubdetector::PixelBarrel)
        pixelDet = id;
      if (stripDet.rawId() == 0 && id.subdetId() == StripSubdetector::TIB)
        stripDet = id;
      if (pixelDet.rawId() != 0 && stripDet.rawId() != 0)
        break;
    }
    if (pixelDet.rawId() == 0 || stripDet.rawId() == 0)
      throw cms::Exception("ToyTrackerDigiProducer")
          << "no pixel-barrel or TIB det unit found in the TrackerGeometry";

    // three adjacent strips, well above the (fake) noise thresholds
    std::vector<edm::DetSet<SiStripDigi>> stripSets(1, edm::DetSet<SiStripDigi>(stripDet.rawId()));
    for (int strip = 100; strip < 103; ++strip)
      stripSets[0].push_back(SiStripDigi(strip, 120));

    // a 2x2 block of pixels
    std::vector<edm::DetSet<PixelDigi>> pixelSets(1, edm::DetSet<PixelDigi>(pixelDet.rawId()));
    for (int row = 20; row < 22; ++row)
      for (int col = 30; col < 32; ++col)
        pixelSets[0].push_back(PixelDigi(row, col, 200));

    edm::LogPrint("ToyTrackerDigiProducer")
        << "toy digis: 3 strip digis on " << stripDet.rawId()
        << ", 4 pixel digis on " << pixelDet.rawId();

    event.put(std::make_unique<edm::DetSetVector<SiStripDigi>>(stripSets));
    event.put(std::make_unique<edm::DetSetVector<PixelDigi>>(pixelSets));
  }
};

class TrackerLocalRecoChecker : public edm::one::EDAnalyzer<> {
public:
  explicit TrackerLocalRecoChecker(const edm::ParameterSet& conf)
      : stripClustersToken_(consumes<edmNew::DetSetVector<SiStripCluster>>(
            conf.getParameter<edm::InputTag>("stripClusters"))),
        pixelClustersToken_(consumes<edmNew::DetSetVector<SiPixelCluster>>(
            conf.getParameter<edm::InputTag>("pixelClusters"))),
        stripHitsToken_(consumes<SiStripRecHit2DCollection>(
            conf.getParameter<edm::InputTag>("stripHits"))),
        pixelHitsToken_(consumes<SiPixelRecHitCollection>(
            conf.getParameter<edm::InputTag>("pixelHits"))) {}

  void analyze(const edm::Event& event, const edm::EventSetup&) override {
    const auto& stripClusters = event.get(stripClustersToken_);
    const auto& pixelClusters = event.get(pixelClustersToken_);
    const auto& stripHits = event.get(stripHitsToken_);
    const auto& pixelHits = event.get(pixelHitsToken_);

    edm::LogPrint("TrackerLocalRecoChecker")
        << "strip clusters: " << stripClusters.dataSize()
        << ", pixel clusters: " << pixelClusters.dataSize()
        << ", strip rec hits: " << stripHits.dataSize()
        << ", pixel rec hits: " << pixelHits.dataSize();

    for (const auto& set : stripHits)
      for (const auto& hit : set)
        edm::LogPrint("TrackerLocalRecoChecker")
            << "strip hit on " << set.detId() << " at local x = " << hit.localPosition().x()
            << " +- " << std::sqrt(hit.localPositionError().xx());
    for (const auto& set : pixelHits)
      for (const auto& hit : set)
        edm::LogPrint("TrackerLocalRecoChecker")
            << "pixel hit on " << set.detId() << " at local (x, y) = ("
            << hit.localPosition().x() << ", " << hit.localPosition().y() << ")";

    if (stripClusters.dataSize() != 1 || pixelClusters.dataSize() != 1 ||
        stripHits.dataSize() != 1 || pixelHits.dataSize() != 1)
      throw cms::Exception("TrackerLocalRecoChecker")
          << "expected exactly one cluster and one rec hit per subdetector";
  }

private:
  edm::EDGetTokenT<edmNew::DetSetVector<SiStripCluster>> stripClustersToken_;
  edm::EDGetTokenT<edmNew::DetSetVector<SiPixelCluster>> pixelClustersToken_;
  edm::EDGetTokenT<SiStripRecHit2DCollection> stripHitsToken_;
  edm::EDGetTokenT<SiPixelRecHitCollection> pixelHitsToken_;
};

#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(ToyTrackerDigiProducer);
DEFINE_FWK_MODULE(TrackerLocalRecoChecker);
