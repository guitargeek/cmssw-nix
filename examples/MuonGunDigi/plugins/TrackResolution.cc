// How well does the fitted track momentum agree with the muon the gun fired?
//
// Everything earlier in this example validates positions. A 9 um rec-hit
// residual says a hit is in the right place; it says nothing about whether
// pattern recognition can assemble hits across nine layers into one
// trajectory, and nothing at all about the magnetic field. Momentum is
// measured from curvature, so the fitted pt is the first number in this chain
// that depends on the field being the same one that bent the muon during
// simulation - a field wrong by a few percent produces hits in exactly the
// right places and a momentum wrong by the same few percent.
//
// The gun fires muons of known pt, so the truth is available: the SimTracks
// that came from the generator carry the momentum Geant4 was given. For each
// of them the analyzer finds the nearest reconstructed track in eta-phi and
// records (pt_rec - pt_gen) / pt_gen.
//
// Charge is checked separately and is not folded into the resolution. A sign
// error in the field or the fit gives a perfectly good |pt| with the
// trajectory bending the wrong way, which a resolution number alone would
// never show.
#include <algorithm>
#include <cmath>
#include <vector>

#include "DataFormats/TrackReco/interface/Track.h"
#include "DataFormats/TrackReco/interface/TrackFwd.h"
#include "DataFormats/TrackReco/interface/HitPattern.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/EDGetToken.h"
#include "FWCore/Utilities/interface/Exception.h"
#include "FWCore/Utilities/interface/InputTag.h"
#include "SimDataFormats/Track/interface/SimTrackContainer.h"

class TrackResolution : public edm::one::EDAnalyzer<> {
public:
  explicit TrackResolution(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;

private:
  const edm::EDGetTokenT<reco::TrackCollection> tracks_;
  const edm::EDGetTokenT<edm::SimTrackContainer> simTracks_;
  const double minPt_;
  const double maxDeltaR_;
  const double maxMedianPtResolution_;
  const double minEfficiency_;
  // Charge agreement is not a constant of nature: it follows the momentum
  // resolution, because the charge *is* the sign of the curvature. A
  // tracker track measured to 0.8% has an unambiguous sign; a standalone
  // muon measured to 20% in the yoke does not, and demanding perfection
  // there would be asserting something untrue.
  const double minChargeAgreement_;
  // The fit chi2 is the only number here that is about the fit rather than
  // about the muon. Everything else can look reasonable while the hits the
  // fit is given are systematically displaced: a bias common to a chamber is
  // absorbed by the segment, and what is left shows up as stations that
  // disagree with each other - which is chi2, and nothing else.
  const double maxMedianChi2_;

  std::vector<double> ptResiduals_;
  // diagnostics: what the vertex producer's track filter would see
  std::vector<double> d0_, dz_, layers_, pixelLayers_, chi2_;
  unsigned long generated_ = 0;
  unsigned long matched_ = 0;
  unsigned long rightCharge_ = 0;
};

TrackResolution::TrackResolution(const edm::ParameterSet& ps)
    : tracks_(consumes<reco::TrackCollection>(ps.getParameter<edm::InputTag>("tracks"))),
      simTracks_(consumes<edm::SimTrackContainer>(ps.getParameter<edm::InputTag>("simTracks"))),
      minPt_(ps.getParameter<double>("minPt")),
      maxDeltaR_(ps.getParameter<double>("maxDeltaR")),
      maxMedianPtResolution_(ps.getParameter<double>("maxMedianPtResolution")),
      minEfficiency_(ps.getParameter<double>("minEfficiency")),
      minChargeAgreement_(ps.getParameter<double>("minChargeAgreement")),
      maxMedianChi2_(ps.getParameter<double>("maxMedianChi2")) {}

void TrackResolution::analyze(const edm::Event& ev, const edm::EventSetup&) {
  edm::Handle<reco::TrackCollection> tracks;
  ev.getByToken(tracks_, tracks);
  if (!tracks.isValid())
    throw cms::Exception("NoTracks") << "the track collection is not in the event";

  edm::Handle<edm::SimTrackContainer> sims;
  ev.getByToken(simTracks_, sims);
  if (!sims.isValid())
    throw cms::Exception("NoSimTracks") << "the SimTrack collection is not in the event";

  for (const auto& sim : *sims) {
    // only the muons the generator produced, not the secondaries Geant4 made
    if (sim.genpartIndex() < 0 || std::abs(sim.type()) != 13)
      continue;
    const double genPt = sim.momentum().pt();
    if (genPt < minPt_)
      continue;
    ++generated_;

    const double genEta = sim.momentum().eta();
    const double genPhi = sim.momentum().phi();

    const reco::Track* best = nullptr;
    double bestDR = -1.0;
    for (const auto& trk : *tracks) {
      double dphi = std::abs(trk.phi() - genPhi);
      if (dphi > M_PI)
        dphi = 2.0 * M_PI - dphi;
      const double dr = std::hypot(trk.eta() - genEta, dphi);
      if (bestDR < 0.0 || dr < bestDR) {
        bestDR = dr;
        best = &trk;
      }
    }
    if (!best || bestDR > maxDeltaR_)
      continue;

    ++matched_;
    ptResiduals_.push_back((best->pt() - genPt) / genPt);
    d0_.push_back(std::abs(best->d0()));
    dz_.push_back(std::abs(best->dz()));
    layers_.push_back(best->hitPattern().trackerLayersWithMeasurement());
    pixelLayers_.push_back(best->hitPattern().pixelLayersWithMeasurement());
    chi2_.push_back(best->normalizedChi2());
    // the gun fires mu+ and mu-; charge is -pdgId/13
    const int genCharge = (sim.type() > 0) ? -1 : 1;
    if (best->charge() == genCharge)
      ++rightCharge_;
  }
}

void TrackResolution::endJob() {
  const double eff = generated_ ? double(matched_) / double(generated_) : 0.0;

  double median = 0.0, rms = 0.0;
  if (!ptResiduals_.empty()) {
    std::vector<double> absres;
    absres.reserve(ptResiduals_.size());
    double sq = 0.0;
    for (double r : ptResiduals_) {
      absres.push_back(std::abs(r));
      sq += r * r;
    }
    std::sort(absres.begin(), absres.end());
    median = absres[absres.size() / 2];
    rms = std::sqrt(sq / double(ptResiduals_.size()));
  }

  auto med = [](std::vector<double> v) {
    if (v.empty()) return 0.0;
    std::sort(v.begin(), v.end());
    return v[v.size() / 2];
  };
  const double medianChi2 = med(chi2_);
  edm::LogWarning("TrackResolution")
      << "  track quality: median |d0| " << 1e4 * med(d0_) << " um, |dz| "
      << 1e4 * med(dz_) << " um, tracker layers " << med(layers_) << ", pixel layers "
      << med(pixelLayers_) << ", chi2/ndof " << medianChi2;

  edm::LogWarning("TrackResolution")
      << "reconstructed " << matched_ << "/" << generated_ << " generated muons ("
      << 100.0 * eff << "%), median |dpt|/pt = " << 100.0 * median << "%, RMS " << 100.0 * rms
      << "%, correct charge " << rightCharge_ << "/" << matched_;

  if (generated_ == 0)
    throw cms::Exception("NoGeneratedMuons")
        << "no generator-level muons in the SimTrack collection - the simulation "
        << "half of this chain did not run";
  if (matched_ == 0)
    throw cms::Exception("NothingReconstructed")
        << "none of the " << generated_ << " generated muons has a track within dR "
        << maxDeltaR_ << ". Hits in the right places do not make a trajectory: this is "
        << "seeding or pattern recognition, not the digitiser.";
  if (eff < minEfficiency_)
    throw cms::Exception("LowEfficiency")
        << "only " << 100.0 * eff << "% of generated muons were reconstructed, required "
        << 100.0 * minEfficiency_ << "%";
  const double chargeAgreement = matched_ ? double(rightCharge_) / double(matched_) : 0.0;
  if (chargeAgreement < minChargeAgreement_)
    throw cms::Exception("WrongCharge")
        << rightCharge_ << " of " << matched_ << " tracks have the generated charge ("
        << 100.0 * chargeAgreement << "%, required " << 100.0 * minChargeAgreement_
        << "%). A "
        << "sign error in the field or the fit bends the trajectory the wrong way while "
        << "leaving |pt| perfectly reasonable.";
  if (median > maxMedianPtResolution_)
    throw cms::Exception("BadMomentumResolution")
        << "median |dpt|/pt is " << 100.0 * median << "%, required below "
        << 100.0 * maxMedianPtResolution_ << "%. The hits are in the right places, so "
        << "this is the momentum measurement itself - most likely the magnetic field "
        << "the fit uses is not the field the muon was bent by.";

  // Checked last, and deliberately after the momentum: if the drift times are
  // decoded with the wrong time-of-flight convention the momentum degrades
  // too, but the momentum bound is loose here on purpose (the yoke really
  // does scatter) and would not catch it. The chi2 does.
  if (medianChi2 > maxMedianChi2_)
    throw cms::Exception("BadFitQuality")
        << "median chi2/ndof is " << medianChi2 << ", required below " << maxMedianChi2_
        << ". The fit does not describe its own hits. A chi2 this large is not a "
        << "resolution problem - it means the hits are displaced from where the "
        << "trajectory says they should be, so look at what was done to them before "
        << "the fit saw them: the drift-time synchronisation has to undo exactly what "
        << "the digitiser applied, correction *type* as well as offset.";

  edm::LogWarning("TrackResolution") << "track momentum OK";
}

DEFINE_FWK_MODULE(TrackResolution);
