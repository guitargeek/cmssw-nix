// Did local reconstruction put the rec hits back where the particle was?
//
// This is the measurement that ties the whole chain together. A rec hit
// position is only correct if the geometry, the drift and Lorentz deflection
// the digitiser applied, the charge sharing between neighbouring channels, the
// cluster charge weighting and the position estimator all agree with one
// another. Any one of them wrong and the reconstructed position walks away
// from the simulated one, usually by far more than the resolution.
//
// So for every SimHit the analyzer finds the nearest rec hit in the same
// module and records the distance in the measured coordinate(s). The expected
// scale is set by the sensor pitch: 80 um strips in the TIB, where a one- or
// two-strip cluster localises to roughly pitch/sqrt(12); 100 x 150 um pixels,
// which do better because the cluster is two-dimensional and charge sharing
// interpolates within a pixel.
//
// Matching this way round - from SimHit to rec hit, never the reverse - is
// deliberate. The strip digitiser puts noise on every channel in the tracker,
// so there are rec hits in thousands of modules no particle ever entered.
// They carry no information about whether reconstruction works and would only
// add a tail.
#include <algorithm>
#include <cmath>
#include <map>
#include <string>
#include <vector>

#include "DataFormats/Common/interface/DetSetVectorNew.h"
#include "DataFormats/TrackerRecHit2D/interface/SiPixelRecHitCollection.h"
#include "DataFormats/TrackerRecHit2D/interface/SiStripRecHit2DCollection.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/EDGetToken.h"
#include "FWCore/Utilities/interface/Exception.h"
#include "FWCore/Utilities/interface/InputTag.h"
#include "SimDataFormats/TrackingHit/interface/PSimHitContainer.h"

namespace {
  // a hit position in the module frame, and how far it is from another one
  struct Point {
    double x = 0.0;
    double y = 0.0;
  };

  struct Tally {
    std::vector<double> residuals;  // the matched distances, cm
    std::vector<double> residualsY;  // for a 2D sensor, the second coordinate
    unsigned long seen = 0;
    unsigned long matched = 0;
  };
}  // namespace

class RecHitResidual : public edm::one::EDAnalyzer<> {
public:
  explicit RecHitResidual(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;

private:
  // Strips measure one coordinate, so only local x is compared. Pixels measure
  // both, so the residual is the distance in the plane.
  std::vector<edm::EDGetTokenT<SiStripRecHit2DCollection>> stripRecHits_;
  std::vector<edm::EDGetTokenT<edm::PSimHitContainer>> stripSimHits_;
  std::vector<edm::EDGetTokenT<SiPixelRecHitCollection>> pixelRecHits_;
  std::vector<edm::EDGetTokenT<edm::PSimHitContainer>> pixelSimHits_;

  const double matchWindow_;
  const double maxStripMedian_;
  const double maxPixelMedian_;
  const double minEfficiency_;

  Tally strip_, pixel_;

  void match(const edm::Event&,
             const std::map<unsigned int, std::vector<Point>>&,
             const std::vector<edm::EDGetTokenT<edm::PSimHitContainer>>&,
             bool twoDimensional,
             Tally&) const;
  void report(const char*, const Tally&, double maxMedian) const;
};

RecHitResidual::RecHitResidual(const edm::ParameterSet& ps)
    : matchWindow_(ps.getParameter<double>("matchWindow")),
      maxStripMedian_(ps.getParameter<double>("maxStripMedianResidual")),
      maxPixelMedian_(ps.getParameter<double>("maxPixelMedianResidual")),
      minEfficiency_(ps.getParameter<double>("minEfficiency")) {
  for (const auto& t : ps.getParameter<std::vector<edm::InputTag>>("stripRecHits"))
    stripRecHits_.push_back(consumes<SiStripRecHit2DCollection>(t));
  for (const auto& t : ps.getParameter<std::vector<edm::InputTag>>("stripSimHits"))
    stripSimHits_.push_back(consumes<edm::PSimHitContainer>(t));
  for (const auto& t : ps.getParameter<std::vector<edm::InputTag>>("pixelRecHits"))
    pixelRecHits_.push_back(consumes<SiPixelRecHitCollection>(t));
  for (const auto& t : ps.getParameter<std::vector<edm::InputTag>>("pixelSimHits"))
    pixelSimHits_.push_back(consumes<edm::PSimHitContainer>(t));
}

void RecHitResidual::match(const edm::Event& ev,
                           const std::map<unsigned int, std::vector<Point>>& byDet,
                           const std::vector<edm::EDGetTokenT<edm::PSimHitContainer>>& tokens,
                           bool twoDimensional,
                           Tally& tally) const {
  for (const auto& token : tokens) {
    edm::Handle<edm::PSimHitContainer> sh;
    ev.getByToken(token, sh);
    if (!sh.isValid())
      continue;
    for (const auto& sim : *sh) {
      ++tally.seen;
      auto it = byDet.find(sim.detUnitId());
      if (it == byDet.end())
        continue;
      const double sx = sim.localPosition().x();
      const double sy = sim.localPosition().y();
      // pick the nearest rec hit by the full distance, but keep the
      // coordinates apart: a strip median and a pixel median are only
      // comparable if both are the measured-coordinate residual
      double best = -1.0;
      double bestX = 0.0, bestY = 0.0;
      for (const auto& p : it->second) {
        const double dx = p.x - sx;
        const double d = twoDimensional ? std::hypot(dx, p.y - sy) : std::abs(dx);
        if (best < 0.0 || d < best) {
          best = d;
          bestX = std::abs(dx);
          bestY = std::abs(p.y - sy);
        }
      }
      if (best >= 0.0 && best < matchWindow_) {
        ++tally.matched;
        tally.residuals.push_back(bestX);
        if (twoDimensional)
          tally.residualsY.push_back(bestY);
      }
    }
  }
}

void RecHitResidual::analyze(const edm::Event& ev, const edm::EventSetup&) {
  std::map<unsigned int, std::vector<Point>> stripByDet;
  bool anyStrip = false;
  for (const auto& token : stripRecHits_) {
    edm::Handle<SiStripRecHit2DCollection> rh;
    ev.getByToken(token, rh);
    if (!rh.isValid())
      continue;
    anyStrip = true;
    for (const auto& ds : *rh)
      for (const auto& hit : ds)
        stripByDet[ds.detId()].push_back({hit.localPosition().x(), hit.localPosition().y()});
  }
  if (!stripRecHits_.empty() && !anyStrip)
    throw cms::Exception("NoRecHits") << "no strip rec hit collection is in the event";
  match(ev, stripByDet, stripSimHits_, false, strip_);

  std::map<unsigned int, std::vector<Point>> pixelByDet;
  bool anyPixel = false;
  for (const auto& token : pixelRecHits_) {
    edm::Handle<SiPixelRecHitCollection> rh;
    ev.getByToken(token, rh);
    if (!rh.isValid())
      continue;
    anyPixel = true;
    for (const auto& ds : *rh)
      for (const auto& hit : ds)
        pixelByDet[ds.detId()].push_back({hit.localPosition().x(), hit.localPosition().y()});
  }
  if (!pixelRecHits_.empty() && !anyPixel)
    throw cms::Exception("NoRecHits") << "no pixel rec hit collection is in the event";
  match(ev, pixelByDet, pixelSimHits_, true, pixel_);
}

void RecHitResidual::report(const char* what, const Tally& t, double maxMedian) const {
  const double eff = t.seen ? double(t.matched) / double(t.seen) : 0.0;

  double median = 0.0, rms = 0.0;
  if (!t.residuals.empty()) {
    std::vector<double> sorted(t.residuals);
    std::sort(sorted.begin(), sorted.end());
    median = sorted[sorted.size() / 2];
    double sq = 0.0;
    for (double r : t.residuals)
      sq += r * r;
    rms = std::sqrt(sq / double(t.residuals.size()));
  }

  double medianY = 0.0;
  if (!t.residualsY.empty()) {
    std::vector<double> sy(t.residualsY);
    std::sort(sy.begin(), sy.end());
    medianY = sy[sy.size() / 2];
  }

  edm::LogWarning("RecHitResidual")
      << "  " << what << ": " << t.matched << "/" << t.seen << " SimHits reconstructed ("
      << 100.0 * eff << "%), median " << 1e4 * median << " um, RMS " << 1e4 * rms << " um"
      << (t.residualsY.empty() ? std::string()
              : "  (second coordinate: median " + std::to_string(1e4 * medianY) + " um)");

  if (t.seen == 0)
    throw cms::Exception("NoSimHits") << what << ": no SimHits to compare against - the "
                                      << "simulation half of this chain did not run";
  if (t.residuals.empty())
    throw cms::Exception("NothingReconstructed")
        << what << ": not one of the " << t.seen << " SimHits has a rec hit within "
        << 1e4 * matchWindow_ << " um in the same module";
  if (eff < minEfficiency_)
    throw cms::Exception("LowEfficiency")
        << what << ": only " << 100.0 * eff << "% of SimHits were reconstructed, required "
        << 100.0 * minEfficiency_ << "%";
  if (median > maxMedian)
    throw cms::Exception("BadResiduals")
        << what << ": median residual is " << 1e4 * median << " um, required below "
        << 1e4 * maxMedian << " um. The rec hits are in the right modules but the wrong "
        << "place in them, which means the geometry, the Lorentz drift applied at "
        << "digitisation and the cluster position estimator do not agree.";
}

void RecHitResidual::endJob() {
  edm::LogWarning("RecHitResidual") << "rec hit residuals:";
  if (!stripRecHits_.empty())
    report("strip", strip_, maxStripMedian_);
  if (!pixelRecHits_.empty())
    report("pixel", pixel_, maxPixelMedian_);
  edm::LogWarning("RecHitResidual") << "rec hit residuals OK";
}

DEFINE_FWK_MODULE(RecHitResidual);
