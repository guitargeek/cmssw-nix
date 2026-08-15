// Toy DT digis along a real muon trajectory, plus a checker for the
// standalone muons reconstructed from them.
//
// The muon local reco example puts hits in a single chamber, which is enough
// for one segment but not for a track. Here a muon of a given pt is shot from
// the origin through all four barrel stations of one sector and stepped
// through the *real* magnetic field - the same volume-based field the
// reconstruction will use, queried from the EventSetup. For every DT layer
// the trajectory crosses, the producer works out which wire the crossing
// falls on and how far from it, and writes a digi with the corresponding
// drift time. The standard DT rec hit / segment reconstruction, the muon seed
// generator and the standalone muon fit then run on those exactly as they
// would on real data.
//
// Stepping through the real field is what makes this a test of the field
// rather than only of the reconstruction: a straight track would come back
// out of the fit under any field at all, whereas the curvature written in
// here is the one the return flux in the yoke produces, so the pt only comes
// back right if the field the fit sees is the same one.

#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/Utilities/interface/Exception.h"

#include <set>

#include "DataFormats/DTDigi/interface/DTDigiCollection.h"
#include "DataFormats/MuonDetId/interface/DTChamberId.h"
#include "DataFormats/MuonDetId/interface/DTLayerId.h"
#include "DataFormats/MuonDetId/interface/DTSuperLayerId.h"
#include "DataFormats/TrackReco/interface/Track.h"
#include "DataFormats/TrackReco/interface/TrackFwd.h"
#include "DataFormats/TrajectorySeed/interface/TrajectorySeedCollection.h"

#include "Geometry/DTGeometry/interface/DTGeometry.h"
#include "Geometry/DTGeometry/interface/DTLayer.h"
#include "Geometry/DTGeometry/interface/DTTopology.h"
#include "Geometry/Records/interface/MuonGeometryRecord.h"

#include "MagneticField/Engine/interface/MagneticField.h"
#include "MagneticField/Records/interface/IdealMagneticFieldRecord.h"

namespace {
  // DT cell drift velocity, cm/ns, and the TDC unit (25 ns / 32 counts)
  constexpr double kDriftVelocity = 0.00543;
  constexpr double kTdcPerNs = 32. / 25.;
  constexpr double kSpeedOfLight = 29.9792458;  // cm/ns
  // 1/R[cm] = kBendingConstant * q * B[T] / pt[GeV]
  constexpr double kBendingConstant = 0.0029979246;
  // trajectory stepping
  constexpr double kStep = 1.0;      // cm
  constexpr double kMaxRadius = 800.;  // cm, past the outermost DT station

  // Step a charged particle of momentum `p` (GeV) from the origin through the
  // field, returning the trajectory as a polyline. Classic RK4 on
  //   dx/ds = p_hat,  dp_hat/ds = (q * kBendingConstant / |p|) * (p_hat x B)
  std::vector<GlobalPoint> stepThroughField(const MagneticField& field, GlobalVector p, int charge) {
    const double momentum = p.mag();
    const double k = charge * kBendingConstant / momentum;

    auto derivative = [&](const GlobalPoint& x, const GlobalVector& dir) {
      const GlobalVector b = field.inTesla(x);
      return GlobalVector(k * (dir.cross(b).x()), k * (dir.cross(b).y()), k * (dir.cross(b).z()));
    };

    std::vector<GlobalPoint> path;
    GlobalPoint x(0., 0., 0.);
    GlobalVector dir = p.unit();
    path.push_back(x);
    while (x.perp() < kMaxRadius && path.size() < 4000) {
      const GlobalVector k1 = derivative(x, dir);
      const GlobalVector d2 = (dir + k1 * (kStep / 2)).unit();
      const GlobalVector k2 = derivative(x + dir * (kStep / 2), d2);
      const GlobalVector d3 = (dir + k2 * (kStep / 2)).unit();
      const GlobalVector k3 = derivative(x + d2 * (kStep / 2), d3);
      const GlobalVector d4 = (dir + k3 * kStep).unit();
      const GlobalVector k4 = derivative(x + d3 * kStep, d4);

      const GlobalVector slope = (k1 + k2 * 2. + k3 * 2. + k4) * (1. / 6.);
      const GlobalVector midDir = (dir + slope * (kStep / 2)).unit();
      x = x + midDir * kStep;
      dir = (dir + slope * kStep).unit();
      path.push_back(x);
    }
    return path;
  }
}  // namespace

class ToyMuonTrackDigiProducer : public edm::stream::EDProducer<> {
public:
  explicit ToyMuonTrackDigiProducer(const edm::ParameterSet& conf)
      : dtToken_(esConsumes<DTGeometry, MuonGeometryRecord>()),
        fieldToken_(esConsumes<MagneticField, IdealMagneticFieldRecord>()),
        wheel_(conf.getParameter<int>("wheel")),
        sector_(conf.getParameter<int>("sector")),
        tTrig_(conf.getParameter<double>("tTrig")),
        pt_(conf.getParameter<double>("pt")),
        charge_(conf.getParameter<int>("charge")) {
    produces<DTDigiCollection>();
  }

  void produce(edm::Event& event, const edm::EventSetup& setup) override {
    const DTGeometry& dtGeom = setup.getData(dtToken_);
    const MagneticField& field = setup.getData(fieldToken_);

    // Aim the muon at the centre of the innermost chamber of the sector: the
    // four stations are stacked radially behind each other, so one direction
    // crosses all of them near their centre.
    const DTChamber* mb1 = dtGeom.chamber(DTChamberId(wheel_, 1, sector_));
    if (!mb1)
      throw cms::Exception("ToyMuonTrackDigiProducer")
          << "no DT chamber for wheel " << wheel_ << " station 1 sector " << sector_;
    const GlobalVector dir = GlobalVector(mb1->surface().position().x(),
                                          mb1->surface().position().y(),
                                          mb1->surface().position().z())
                                 .unit();
    const std::vector<GlobalPoint> path =
        stepThroughField(field, dir * (pt_ / dir.perp()), charge_);

    auto digis = std::make_unique<DTDigiCollection>();
    int nDigis = 0;
    std::set<DTChamberId> chambersHit;
    // Every chamber is tested for a crossing rather than only the ones of the
    // sector aimed at: a muon of a few tens of GeV bends by an appreciable
    // fraction of a sector on its way out, so which chambers it actually
    // traverses is for the trajectory to decide.
    for (const DTChamber* chamber : dtGeom.chambers()) {
      // superlayers 1 and 3 measure phi; superlayer 2 (theta) does not exist
      // in station 4, so the track is reconstructed from the phi views only
      for (int sl : {1, 3}) {
        const DTSuperLayer* superLayer = chamber->superLayer(DTSuperLayerId(chamber->id(), sl));
        if (!superLayer)
          continue;
        for (const DTLayer* layer : superLayer->layers()) {
          // walk the trajectory until it changes side of the layer plane, and
          // interpolate the crossing inside that step
          const auto& plane = layer->surface();
          const GlobalVector normal(plane.normalVector().x(), plane.normalVector().y(),
                                    plane.normalVector().z());
          const GlobalVector toPlane(plane.position().x(), plane.position().y(),
                                     plane.position().z());
          const double offset = normal.dot(toPlane);
          auto sideOf = [&](const GlobalPoint& p) {
            return normal.x() * p.x() + normal.y() * p.y() + normal.z() * p.z() - offset;
          };

          GlobalPoint crossing;
          bool found = false;
          for (size_t i = 1; i < path.size(); ++i) {
            const double d0 = sideOf(path[i - 1]);
            const double d1 = sideOf(path[i]);
            if (d0 == 0. || (d0 < 0.) != (d1 < 0.)) {
              const double f = d0 / (d0 - d1);
              crossing = GlobalPoint(path[i - 1].x() + f * (path[i].x() - path[i - 1].x()),
                                     path[i - 1].y() + f * (path[i].y() - path[i - 1].y()),
                                     path[i - 1].z() + f * (path[i].z() - path[i - 1].z()));
              found = true;
              break;
            }
          }
          if (!found)
            continue;
          const LocalPoint local = layer->toLocal(crossing);
          // the crossing has to be on the physical layer, not on the infinite
          // plane through it
          if (!plane.bounds().inside(local))
            continue;

          const DTTopology& topology = layer->specificTopology();
          const int wire = topology.channel(local);
          if (!topology.isWireValid(wire))
            continue;
          const double drift = std::abs(local.x() - topology.wirePosition(wire));
          // a crossing further from the wire than half a cell is not in this
          // cell at all
          if (drift > topology.cellWidth() / 2)
            continue;
          // the reconstruction subtracts the time of flight from the vertex
          // (DTTTrigSyncTOFCorr), so the digi has to carry it
          const double timeOfFlight = crossing.mag() / kSpeedOfLight;
          const int tdc =
              static_cast<int>((tTrig_ + timeOfFlight + drift / kDriftVelocity) * kTdcPerNs);

          digis->insertDigi(layer->id(), DTDigi(wire, tdc, 0));
          chambersHit.insert(chamber->id());
          ++nDigis;
        }
      }
    }

    edm::LogPrint("ToyMuonTrackDigiProducer")
        << "muon pt = " << pt_ << " GeV, charge " << charge_ << ", along (" << dir.x() << ", "
        << dir.y() << ", " << dir.z() << "): " << nDigis << " DT digis in wheel " << wheel_
        << " sector " << sector_ << ", crossing " << chambersHit.size() << " chambers";

    event.put(std::move(digis));
  }

private:
  edm::ESGetToken<DTGeometry, MuonGeometryRecord> dtToken_;
  edm::ESGetToken<MagneticField, IdealMagneticFieldRecord> fieldToken_;
  const int wheel_;
  const int sector_;
  const double tTrig_;
  const double pt_;
  const int charge_;
};

class StandAloneMuonChecker : public edm::one::EDAnalyzer<> {
public:
  explicit StandAloneMuonChecker(const edm::ParameterSet& conf)
      : seedsToken_(consumes<TrajectorySeedCollection>(conf.getParameter<edm::InputTag>("seeds"))),
        tracksToken_(consumes<reco::TrackCollection>(conf.getParameter<edm::InputTag>("tracks"))),
        minTracks_(conf.getParameter<unsigned int>("minTracks")),
        minPt_(conf.getParameter<double>("minPt")),
        maxPt_(conf.getParameter<double>("maxPt")),
        charge_(conf.getParameter<int>("charge")) {}

  void analyze(const edm::Event& event, const edm::EventSetup&) override {
    const auto& seeds = event.get(seedsToken_);
    const auto& tracks = event.get(tracksToken_);

    edm::LogPrint("StandAloneMuonChecker")
        << "muon seeds: " << seeds.size() << ", standalone muons: " << tracks.size();

    for (const auto& track : tracks)
      edm::LogPrint("StandAloneMuonChecker")
          << "  standalone muon: pt = " << track.pt() << " GeV, eta = " << track.eta()
          << ", phi = " << track.phi() << ", charge = " << track.charge()
          << ", hits = " << track.numberOfValidHits() << ", chi2/ndof = " << track.normalizedChi2();

    if (tracks.size() < minTracks_)
      throw cms::Exception("StandAloneMuonChecker")
          << "expected at least " << minTracks_ << " standalone muon(s), got " << tracks.size();

    for (const auto& track : tracks) {
      if (track.pt() < minPt_ || track.pt() > maxPt_)
        throw cms::Exception("StandAloneMuonChecker")
            << "standalone muon pt = " << track.pt() << " GeV is outside the expected [" << minPt_
            << ", " << maxPt_ << "] GeV";
      if (track.charge() != charge_)
        throw cms::Exception("StandAloneMuonChecker")
            << "standalone muon charge " << track.charge() << " != expected " << charge_;
    }
  }

private:
  edm::EDGetTokenT<TrajectorySeedCollection> seedsToken_;
  edm::EDGetTokenT<reco::TrackCollection> tracksToken_;
  const unsigned int minTracks_;
  const double minPt_;
  const double maxPt_;
  const int charge_;
};

DEFINE_FWK_MODULE(ToyMuonTrackDigiProducer);
DEFINE_FWK_MODULE(StandAloneMuonChecker);
