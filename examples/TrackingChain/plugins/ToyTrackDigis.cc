// Toy track digi producer + reco checker for the full tracking chain: place
// pixel/strip digis along true helices (uniform 3.8 T field) through the
// barrel of the XML-built TrackerGeometry, then let the standard local reco,
// pixel-track fitting and primary-vertex reconstruction run on them.

#include <cmath>

#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/ESHandle.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/Utilities/interface/Exception.h"

#include "DataFormats/Common/interface/DetSetVector.h"
#include "DataFormats/SiPixelDigi/interface/PixelDigi.h"
#include "DataFormats/SiStripDigi/interface/SiStripDigi.h"
#include "DataFormats/TrackReco/interface/Track.h"
#include "DataFormats/VertexReco/interface/Vertex.h"
#include "DataFormats/VertexReco/interface/VertexFwd.h"

#include "Geometry/TrackerGeometryBuilder/interface/TrackerGeometry.h"
// PixelGeomDetUnit.h moved package between the two releases -
// Geometry/TrackerGeometryBuilder in 10_6, Geometry/CommonTopologies in 20_1 -
// while StripGeomDetUnit.h, next to it in 10_6, did not move.
#if __has_include("Geometry/TrackerGeometryBuilder/interface/PixelGeomDetUnit.h")
#include "Geometry/TrackerGeometryBuilder/interface/PixelGeomDetUnit.h"
#else
#include "Geometry/CommonTopologies/interface/PixelGeomDetUnit.h"
#endif
#include "Geometry/TrackerGeometryBuilder/interface/StripGeomDetUnit.h"
#include "Geometry/CommonTopologies/interface/PixelTopology.h"
#include "Geometry/CommonTopologies/interface/StripTopology.h"
#include "Geometry/Records/interface/TrackerDigiGeometryRecord.h"
#include "DataFormats/GeometrySurface/interface/Plane.h"

namespace {
  struct ToyTrack {
    double pt, phi0, eta;
    int charge;
  };

  // helix through the origin: signed curvature kappa = q * 0.3 * B / (100 pt)
  // (1/cm), transverse arc length s
  GlobalPoint helixPoint(const ToyTrack& t, double kappa, double s) {
    const double cotTheta = std::sinh(t.eta);
    const double x = (std::sin(t.phi0 + kappa * s) - std::sin(t.phi0)) / kappa;
    const double y = (-std::cos(t.phi0 + kappa * s) + std::cos(t.phi0)) / kappa;
    return GlobalPoint(x, y, s * cotTheta);
  }
}  // namespace

class ToyTrackDigiProducer : public edm::stream::EDProducer<> {
public:
  explicit ToyTrackDigiProducer(const edm::ParameterSet& conf)
      : bField_(conf.getParameter<double>("bField")),
        // the token form of EventSetup access: the legacy
        // setup.get<Record>().get(handle) is gone in 20_1, and this works in
        // both releases
        geomToken_(esConsumes<TrackerGeometry, TrackerDigiGeometryRecord>()) {
    for (const auto& ps : conf.getParameter<std::vector<edm::ParameterSet>>("tracks"))
      tracks_.push_back(ToyTrack{ps.getParameter<double>("pt"),
                                 ps.getParameter<double>("phi"),
                                 ps.getParameter<double>("eta"),
                                 ps.getParameter<int>("charge")});
    produces<edm::DetSetVector<PixelDigi>>();
    produces<edm::DetSetVector<SiStripDigi>>();
  }

  void produce(edm::Event& event, const edm::EventSetup& setup) override {
    const TrackerGeometry& geom = setup.getData(geomToken_);

    std::map<uint32_t, std::vector<PixelDigi>> pixelsByDet;
    std::map<uint32_t, std::map<int, int>> stripsByDet;
    unsigned nPixelHits = 0, nStripHits = 0;

    for (const auto& track : tracks_) {
      // CMS convention: a positive charge in +Bz curves towards negative phi
      const double kappa = -track.charge * 0.3 * bField_ / (100. * track.pt);
      for (const auto* det : geom.detUnits()) {
        const double rDet = det->surface().position().perp();
        if (rDet < 2. || rDet > 115.)
          continue;
        // arc length where the helix reaches the module radius, refined onto
        // the module plane with a few Newton steps
        const double arg = rDet * std::abs(kappa) / 2.;
        if (arg >= 1.)
          continue;
        double s = 2. / std::abs(kappa) * std::asin(arg);
        bool onPlane = false;
        for (int iter = 0; iter < 5; ++iter) {
          const LocalPoint lp = det->surface().toLocal(helixPoint(track, kappa, s));
          if (std::abs(lp.z()) < 1e-3) {
            onPlane = true;
            break;
          }
          const LocalPoint lp2 =
              det->surface().toLocal(helixPoint(track, kappa, s + 0.1));
          const double dzds = (lp2.z() - lp.z()) / 0.1;
          if (std::abs(dzds) < 1e-6)
            break;
          s -= lp.z() / dzds;
          if (s < 0 || s > 300.)
            break;
        }
        if (!onPlane)
          continue;
        const LocalPoint lp = det->surface().toLocal(helixPoint(track, kappa, s));
        if (!det->surface().bounds().inside(LocalPoint(lp.x(), lp.y(), 0)))
          continue;

        if (const auto* pixelDet = dynamic_cast<const PixelGeomDetUnit*>(det)) {
          // split the charge between adjacent pixels according to the
          // sub-pixel position, so the CPE can interpolate
          const auto mp = pixelDet->specificTopology().measurementPosition(lp);
          const int row = int(mp.x()), col = int(mp.y());
          if (row < 1 || col < 1)
            continue;
          const double fRow = mp.x() - row, fCol = mp.y() - col;
          auto& pixels = pixelsByDet[det->geographicalId().rawId()];
          const int rowB = fRow > 0.5 ? row + 1 : row - 1;
          const int colB = fCol > 0.5 ? col + 1 : col - 1;
          const double wRow = std::abs(fRow - 0.5), wCol = std::abs(fCol - 0.5);
          pixels.emplace_back(row, col, int(300 * (1. - wRow) * (1. - wCol)) + 40);
          pixels.emplace_back(rowB, col, int(300 * wRow * (1. - wCol)) + 40);
          pixels.emplace_back(row, colB, int(300 * (1. - wRow) * wCol) + 40);
          ++nPixelHits;
        } else if (const auto* stripDet = dynamic_cast<const StripGeomDetUnit*>(det)) {
          const double stripPos = stripDet->specificTopology().strip(lp);
          const int strip = int(stripPos);
          if (strip < 1 || strip >= stripDet->specificTopology().nstrips() - 1)
            continue;
          const double f = stripPos - strip;
          auto& strips = stripsByDet[det->geographicalId().rawId()];
          const int stripB = f > 0.5 ? strip + 1 : strip - 1;
          const double w = std::abs(f - 0.5);
          strips[strip] += int(200 * (1. - w)) + 30;
          strips[stripB] += int(200 * w) + 30;
          ++nStripHits;
        }
      }
    }

    auto pixelDigis = std::make_unique<edm::DetSetVector<PixelDigi>>();
    for (const auto& [id, digis] : pixelsByDet) {
      edm::DetSet<PixelDigi> ds(id);
      for (const auto& d : digis)
        ds.push_back(d);
      pixelDigis->insert(ds);
    }
    auto stripDigis = std::make_unique<edm::DetSetVector<SiStripDigi>>();
    for (const auto& [id, strips] : stripsByDet) {
      edm::DetSet<SiStripDigi> ds(id);
      for (const auto& [strip, adc] : strips)
        ds.push_back(SiStripDigi(strip, std::min(adc, 250)));
      stripDigis->insert(ds);
    }

    edm::LogPrint("ToyTrackDigiProducer")
        << "toy digis for " << tracks_.size() << " tracks: " << nPixelHits
        << " pixel hits, " << nStripHits << " strip hits";

    event.put(std::move(pixelDigis));
    event.put(std::move(stripDigis));
  }

private:
  double bField_;
  const edm::ESGetToken<TrackerGeometry, TrackerDigiGeometryRecord> geomToken_;
  std::vector<ToyTrack> tracks_;
};

class TrackingChainChecker : public edm::one::EDAnalyzer<> {
public:
  explicit TrackingChainChecker(const edm::ParameterSet& conf)
      : tracksToken_(consumes<reco::TrackCollection>(conf.getParameter<edm::InputTag>("tracks"))),
        verticesToken_(consumes<reco::VertexCollection>(conf.getParameter<edm::InputTag>("vertices"))),
        minTracks_(conf.getParameter<unsigned>("minTracks")) {}

  void analyze(const edm::Event& event, const edm::EventSetup&) override {
    const auto& tracks = event.get(tracksToken_);
    const auto& vertices = event.get(verticesToken_);

    edm::LogPrint("TrackingChainChecker")
        << "reconstructed " << tracks.size() << " tracks, " << vertices.size()
        << " primary vertices";
    for (const auto& t : tracks)
      edm::LogPrint("TrackingChainChecker")
          << "track: pt = " << t.pt() << " GeV, eta = " << t.eta()
          << ", phi = " << t.phi() << ", q = " << t.charge()
          << ", hits = " << t.found() << ", chi2/ndof = " << t.normalizedChi2();
    for (const auto& v : vertices)
      edm::LogPrint("TrackingChainChecker")
          << "vertex: (" << v.x() << ", " << v.y() << ", " << v.z()
          << ") with " << v.tracksSize() << " tracks";

    if (tracks.size() < minTracks_)
      throw cms::Exception("TrackingChainChecker")
          << "expected at least " << minTracks_ << " reconstructed tracks";
    if (vertices.empty() || vertices.front().tracksSize() < minTracks_)
      throw cms::Exception("TrackingChainChecker")
          << "expected a primary vertex with at least " << minTracks_ << " tracks";
  }

private:
  edm::EDGetTokenT<reco::TrackCollection> tracksToken_;
  edm::EDGetTokenT<reco::VertexCollection> verticesToken_;
  unsigned minTracks_;
};

#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(ToyTrackDigiProducer);
DEFINE_FWK_MODULE(TrackingChainChecker);
