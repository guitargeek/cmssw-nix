// Reads back what the tracking validation wrote, after the harvesting.
//
// The standard tracking validation (Validation/RecoTrack's MultiTrackValidator)
// does not decide anything: it fills histograms into the DQM store - how many
// simulated particles there were, per eta bin, how many of them a track was
// associated to, how many tracks were reconstructed and how many of those
// matched a simulated particle - and leaves the verdict to whoever looks at
// the plots. The harvesting step (DQMGenericClient, as configured by
// Validation/RecoTrack's PostProcessorTracker) then divides the counts into
// the efficiency and fake-rate plots that a release validation compares.
//
// This harvester runs after both, at the end of the run - which is when the
// DQM store still holds the run's histograms, and when DQMGenericClient does
// its own work - and turns the plots into numbers with
// bounds: the efficiency and fake rate summed over all bins, the duplicate
// rate, the width of the 1/p pull (are the track errors the right size?),
// and whether the harvested efficiency histogram agrees with the counts it
// was computed from - which is the check that the harvesting ran at all.
#include <cmath>
#include <string>

#include "DQMServices/Core/interface/DQMEDHarvester.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/Exception.h"

class TrackValidationCheck : public DQMEDHarvester {
public:
  explicit TrackValidationCheck(const edm::ParameterSet&);
  void dqmEndRun(DQMStore::IBooker&, DQMStore::IGetter&, edm::Run const&, edm::EventSetup const&) override;
  void dqmEndJob(DQMStore::IBooker&, DQMStore::IGetter&) override {}

private:
  const std::string folder_;
  const double minEfficiency_, maxFakeRate_, maxDuplicateRate_;
  const double minPullWidth_, maxPullWidth_;
};

TrackValidationCheck::TrackValidationCheck(const edm::ParameterSet& ps)
    : folder_(ps.getParameter<std::string>("folder")),
      minEfficiency_(ps.getParameter<double>("minEfficiency")),
      maxFakeRate_(ps.getParameter<double>("maxFakeRate")),
      maxDuplicateRate_(ps.getParameter<double>("maxDuplicateRate")),
      minPullWidth_(ps.getParameter<double>("minPullWidth")),
      maxPullWidth_(ps.getParameter<double>("maxPullWidth")) {}

void TrackValidationCheck::dqmEndRun(DQMStore::IBooker&,
                                     DQMStore::IGetter& getter,
                                     edm::Run const&,
                                     edm::EventSetup const&) {
  auto get = [&](const std::string& name) {
    auto* me = getter.get(folder_ + "/" + name);
    if (!me)
      throw cms::Exception("TrackValidationCheck") << "no " << folder_ << "/" << name << " in the DQM store";
    return me;
  };
  // the sum over the in-range bins; the validation's eta range covers the gun's
  auto sum = [](const auto* me) {
    double s = 0;
    for (int i = 1; i <= me->getNbinsX(); ++i)
      s += me->getBinContent(i);
    return s;
  };

  const auto* simulated = get("num_simul_eta");
  const auto* found = get("num_assoc(simToReco)_eta");
  const double nSimulated = sum(simulated), nFound = sum(found);
  const double nReco = sum(get("num_reco_eta"));
  const double nRecoMatched = sum(get("num_assoc(recoToSim)_eta"));
  const double nDuplicate = sum(get("num_duplicate_eta"));
  if (nSimulated == 0 || nReco == 0)
    throw cms::Exception("TrackValidationCheck") << nSimulated << " simulated particles and " << nReco
                                                 << " tracks: the validation saw nothing";
  const double efficiency = nFound / nSimulated;
  const double fakeRate = 1 - nRecoMatched / nReco;
  const double duplicateRate = nDuplicate / nReco;

  // The harvested efficiency, per bin, weighted back by the bin's count of
  // simulated particles, has to give the same overall number.
  const auto* effic = get("effic");
  double weighted = 0;
  for (int i = 1; i <= simulated->getNbinsX(); ++i)
    weighted += effic->getBinContent(i) * simulated->getBinContent(i);
  const double harvested = weighted / nSimulated;

  const double pullWidth = get("pullQoverp")->getRMS();

  edm::LogPrint("TrackValidationCheck") << "tracking validation: efficiency " << nFound << "/" << nSimulated
                                        << " (harvested " << harvested << "), fake rate " << fakeRate << " of " << nReco
                                        << " tracks, duplicate rate " << duplicateRate << ", q/p pull RMS "
                                        << pullWidth;

  if (std::abs(harvested - efficiency) > 1e-6)
    throw cms::Exception("TrackValidationCheck")
        << "harvested efficiency " << harvested << " does not reproduce the counts' " << efficiency;
  if (efficiency < minEfficiency_)
    throw cms::Exception("TrackValidationCheck") << "efficiency " << efficiency << " below " << minEfficiency_;
  if (fakeRate > maxFakeRate_)
    throw cms::Exception("TrackValidationCheck") << "fake rate " << fakeRate << " above " << maxFakeRate_;
  if (duplicateRate > maxDuplicateRate_)
    throw cms::Exception("TrackValidationCheck") << "duplicate rate " << duplicateRate << " above " << maxDuplicateRate_;
  if (pullWidth < minPullWidth_ || pullWidth > maxPullWidth_)
    throw cms::Exception("TrackValidationCheck")
        << "q/p pull RMS " << pullWidth << " outside [" << minPullWidth_ << ", " << maxPullWidth_ << "]";
}

DEFINE_FWK_MODULE(TrackValidationCheck);
