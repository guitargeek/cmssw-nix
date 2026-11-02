// Does every muon the gun fired fire the Level-1 trigger?
//
// The L1 trigger decides within 4 us whether an event is kept, from coarse
// data the detector sends at every bunch crossing. For a muon in the barrel
// that is the chain the job runs: DT trigger primitives (segments the chamber
// electronics finds), TwinMux, the Kalman barrel track finder, and the global
// muon trigger (uGMT), whose output the L1 menu cuts on.
//
// For each simulated muon this looks for the closest L1 muon in the triggered
// bunch crossing, by the uGMT's own extrapolation of the track back to the
// vertex (etaAtVtx, phiAtVtx), and asks what a trigger efficiency study asks:
// was the muon found, with a quality the single-muon seeds accept, the right
// charge, and a transverse momentum roughly right? The L1 measurement is
// coarse by design (a few bits of hardware precision, 0.5 GeV pt steps), so
// the bounds are on the median of pt(L1)/pt(true), not per muon.
#include <algorithm>
#include <cmath>
#include <vector>

#include "DataFormats/L1Trigger/interface/Muon.h"
#include "DataFormats/Math/interface/deltaR.h"
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

class L1MuonMatch : public edm::one::EDAnalyzer<> {
public:
  explicit L1MuonMatch(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;

private:
  const edm::EDGetTokenT<edm::SimTrackContainer> simTracks_;
  const edm::EDGetTokenT<l1t::MuonBxCollection> l1Muons_;
  const double maxDeltaR_;
  const int minQuality_;
  const double minEfficiency_;
  const double minChargeAgreement_;
  const double minMedianPtRatio_, maxMedianPtRatio_;

  unsigned muons_ = 0, matched_ = 0, chargeRight_ = 0, l1InOtherBx_ = 0;
  std::vector<double> ptRatios_;
};

L1MuonMatch::L1MuonMatch(const edm::ParameterSet& ps)
    : simTracks_(consumes<edm::SimTrackContainer>(ps.getParameter<edm::InputTag>("simTracks"))),
      l1Muons_(consumes<l1t::MuonBxCollection>(ps.getParameter<edm::InputTag>("l1Muons"))),
      maxDeltaR_(ps.getParameter<double>("maxDeltaR")),
      minQuality_(ps.getParameter<int>("minQuality")),
      minEfficiency_(ps.getParameter<double>("minEfficiency")),
      minChargeAgreement_(ps.getParameter<double>("minChargeAgreement")),
      minMedianPtRatio_(ps.getParameter<double>("minMedianPtRatio")),
      maxMedianPtRatio_(ps.getParameter<double>("maxMedianPtRatio")) {}

void L1MuonMatch::analyze(const edm::Event& event, const edm::EventSetup&) {
  const auto& l1 = event.get(l1Muons_);
  for (int bx = l1.getFirstBX(); bx <= l1.getLastBX(); ++bx)
    if (bx != 0)
      l1InOtherBx_ += l1.size(bx);

  for (const auto& sim : event.get(simTracks_)) {
    // the gun's muons: primary (they have a generator particle), |pdg id| 13
    if (std::abs(sim.type()) != 13 || sim.noGenpart())
      continue;
    ++muons_;
    const auto& p = sim.momentum();
    const l1t::Muon* best = nullptr;
    double bestDR = maxDeltaR_;
    for (auto mu = l1.begin(0); mu != l1.end(0); ++mu) {
      if (mu->hwQual() < minQuality_)
        continue;
      const double dR = reco::deltaR(p.eta(), p.phi(), mu->etaAtVtx(), mu->phiAtVtx());
      if (dR < bestDR) {
        bestDR = dR;
        best = &*mu;
      }
    }
    if (!best) {
      edm::LogWarning("L1MuonMatch") << "no L1 muon for the simulated muon with pt " << p.pt() << ", eta " << p.eta()
                                     << ", phi " << p.phi();
      continue;
    }
    ++matched_;
    const int simCharge = sim.type() > 0 ? -1 : +1;  // 13 is the mu-
    if (best->hwChargeValid() && best->charge() == simCharge)
      ++chargeRight_;
    ptRatios_.push_back(best->pt() / p.pt());
    edm::LogInfo("L1MuonMatch") << "pt " << p.pt() << " -> " << best->pt() << ", eta " << p.eta() << " -> "
                                << best->etaAtVtx() << ", phi " << p.phi() << " -> " << best->phiAtVtx()
                                << ", quality " << best->hwQual();
  }
}

void L1MuonMatch::endJob() {
  if (muons_ == 0)
    throw cms::Exception("L1MuonMatch") << "no simulated muons";
  double median = 0;
  if (!ptRatios_.empty()) {
    auto mid = ptRatios_.begin() + ptRatios_.size() / 2;
    std::nth_element(ptRatios_.begin(), mid, ptRatios_.end());
    median = *mid;
  }
  const double efficiency = double(matched_) / muons_;
  const double chargeAgreement = matched_ ? double(chargeRight_) / matched_ : 0;
  edm::LogPrint("L1MuonMatch") << "L1 muons: " << matched_ << "/" << muons_ << " simulated muons triggered"
                               << " (quality >= " << minQuality_ << "), " << chargeRight_ << "/" << matched_
                               << " with the right charge, median pt(L1)/pt(true) " << median << "; "
                               << l1InOtherBx_ << " L1 muons outside the triggered bunch crossing";
  if (efficiency < minEfficiency_)
    throw cms::Exception("L1MuonMatch") << "trigger efficiency " << efficiency << " below " << minEfficiency_;
  if (chargeAgreement < minChargeAgreement_)
    throw cms::Exception("L1MuonMatch") << "charge agreement " << chargeAgreement << " below " << minChargeAgreement_;
  if (median < minMedianPtRatio_ || median > maxMedianPtRatio_)
    throw cms::Exception("L1MuonMatch") << "median pt(L1)/pt(true) " << median << " outside [" << minMedianPtRatio_
                                        << ", " << maxMedianPtRatio_ << "]";
}

DEFINE_FWK_MODULE(L1MuonMatch);
