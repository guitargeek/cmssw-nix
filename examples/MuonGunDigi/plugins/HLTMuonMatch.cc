// Which muons the gun fired does the HLT path keep, and which does it not?
//
// Every HLT filter that accepts an event stores the objects it accepted it
// for (a trigger::TriggerFilterObjectWithRefs): the L1 filter the L1 muons
// that fired the seed, the L2 filter the standalone muons above its
// threshold. Those objects are what physics analyses later match their own
// muons to, to know which of them fired the trigger.
//
// This does the same with the simulated muons. A muon well above the
// path's L1 threshold (18 GeV) has to be among the accepted objects of both
// filters; one below it may or may not be, and is only counted - the
// trigger "turn-on" is where an efficiency study would look. For the
// matched L2 muons, the bound is on the median of pt(L2)/pt(true): the L2
// fit uses the muon chambers alone, so it is coarse, but it is what the
// later steps of the path start from.
#include <algorithm>
#include <cmath>
#include <vector>

#include "DataFormats/HLTReco/interface/TriggerFilterObjectWithRefs.h"
#include "DataFormats/L1Trigger/interface/Muon.h"
#include "DataFormats/Math/interface/deltaR.h"
#include "DataFormats/RecoCandidate/interface/RecoChargedCandidate.h"
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

class HLTMuonMatch : public edm::one::EDAnalyzer<> {
public:
  explicit HLTMuonMatch(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;

private:
  const edm::EDGetTokenT<edm::SimTrackContainer> simTracks_;
  const edm::EDGetTokenT<trigger::TriggerFilterObjectWithRefs> l1Filter_, l2Filter_;
  const double maxDeltaR_;
  const double plateauPt_;
  const double minEfficiency_;
  const double minMedianPtRatio_, maxMedianPtRatio_;

  unsigned events_ = 0, accepted_ = 0;
  unsigned plateau_ = 0, plateauL1_ = 0, plateauL2_ = 0;
  unsigned below_ = 0, belowL2_ = 0;
  std::vector<double> ptRatios_;
};

HLTMuonMatch::HLTMuonMatch(const edm::ParameterSet& ps)
    : simTracks_(consumes<edm::SimTrackContainer>(ps.getParameter<edm::InputTag>("simTracks"))),
      l1Filter_(consumes<trigger::TriggerFilterObjectWithRefs>(ps.getParameter<edm::InputTag>("l1Filter"))),
      l2Filter_(consumes<trigger::TriggerFilterObjectWithRefs>(ps.getParameter<edm::InputTag>("l2Filter"))),
      maxDeltaR_(ps.getParameter<double>("maxDeltaR")),
      plateauPt_(ps.getParameter<double>("plateauPt")),
      minEfficiency_(ps.getParameter<double>("minEfficiency")),
      minMedianPtRatio_(ps.getParameter<double>("minMedianPtRatio")),
      maxMedianPtRatio_(ps.getParameter<double>("maxMedianPtRatio")) {}

void HLTMuonMatch::analyze(const edm::Event& event, const edm::EventSetup&) {
  ++events_;
  // A filter's product is there only if the path got as far as the filter;
  // it holds objects only if the filter accepted the event.
  std::vector<l1t::MuonRef> l1;
  std::vector<reco::RecoChargedCandidateRef> l2;
  if (auto h = event.getHandle(l1Filter_); h.isValid())
    h->getObjects(trigger::TriggerL1Mu, l1);
  if (auto h = event.getHandle(l2Filter_); h.isValid())
    h->getObjects(trigger::TriggerMuon, l2);
  if (!l2.empty())
    ++accepted_;

  for (const auto& sim : event.get(simTracks_)) {
    // the gun's muons: primary (they have a generator particle), |pdg id| 13
    if (std::abs(sim.type()) != 13 || sim.noGenpart())
      continue;
    const auto& p = sim.momentum();
    // the L1 muon by the uGMT's extrapolation to the vertex, the L2 muon by
    // its direction at the vertex
    const bool inL1 = std::any_of(l1.begin(), l1.end(), [&](const auto& mu) {
      return reco::deltaR(p.eta(), p.phi(), mu->etaAtVtx(), mu->phiAtVtx()) < maxDeltaR_;
    });
    const reco::RecoChargedCandidate* inL2 = nullptr;
    double bestDR = maxDeltaR_;
    for (const auto& mu : l2) {
      const double dR = reco::deltaR(p.eta(), p.phi(), mu->eta(), mu->phi());
      if (dR < bestDR) {
        bestDR = dR;
        inL2 = &*mu;
      }
    }
    edm::LogInfo("HLTMuonMatch") << "pt " << p.pt() << ", eta " << p.eta() << ": L1 " << (inL1 ? "yes" : "no")
                                 << ", L2 " << (inL2 ? inL2->pt() : 0.);
    if (p.pt() >= plateauPt_) {
      ++plateau_;
      plateauL1_ += inL1;
      plateauL2_ += inL2 != nullptr;
      if (!inL2)
        edm::LogWarning("HLTMuonMatch") << "the muon with pt " << p.pt() << ", eta " << p.eta() << ", phi " << p.phi()
                                        << " did not pass the path (L1 filter: " << (inL1 ? "yes" : "no") << ")";
    } else {
      ++below_;
      belowL2_ += inL2 != nullptr;
    }
    if (inL2)
      ptRatios_.push_back(inL2->pt() / p.pt());
  }
}

void HLTMuonMatch::endJob() {
  if (plateau_ == 0)
    throw cms::Exception("HLTMuonMatch") << "no simulated muons above " << plateauPt_ << " GeV";
  double median = 0;
  if (!ptRatios_.empty()) {
    auto mid = ptRatios_.begin() + ptRatios_.size() / 2;
    std::nth_element(ptRatios_.begin(), mid, ptRatios_.end());
    median = *mid;
  }
  const double efficiency = double(plateauL2_) / plateau_;
  edm::LogPrint("HLTMuonMatch") << "HLT: " << accepted_ << "/" << events_ << " events accepted; muons above "
                                << plateauPt_ << " GeV: " << plateauL1_ << "/" << plateau_ << " at L1, " << plateauL2_
                                << "/" << plateau_ << " at L2; below: " << belowL2_ << "/" << below_
                                << " at L2; median pt(L2)/pt(true) " << median;
  if (efficiency < minEfficiency_)
    throw cms::Exception("HLTMuonMatch") << "efficiency above " << plateauPt_ << " GeV " << efficiency << " below "
                                         << minEfficiency_;
  if (median < minMedianPtRatio_ || median > maxMedianPtRatio_)
    throw cms::Exception("HLTMuonMatch") << "median pt(L2)/pt(true) " << median << " outside [" << minMedianPtRatio_
                                         << ", " << maxMedianPtRatio_ << "]";
}

DEFINE_FWK_MODULE(HLTMuonMatch);
