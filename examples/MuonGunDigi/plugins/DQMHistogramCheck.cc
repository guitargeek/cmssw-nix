// Reads back what the subsystem DQM modules filled, at the end of the run.
//
// A DQM module, like a validation, decides nothing: it books histograms into
// the DQM store and fills them, and the shifter - or, offline, the release
// comparison - looks at them. Here there is no shifter and no reference, so
// this harvester takes a list of histograms by their full DQM path and puts
// bounds on each: a minimum number of entries (did the module see the data
// at all?) and a window for the mean (is what it saw the right size?). It
// prints every value it checks, so the bounds can be set from a run.
#include <string>
#include <vector>

#include "DQMServices/Core/interface/DQMEDHarvester.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/Exception.h"

class DQMHistogramCheck : public DQMEDHarvester {
public:
  explicit DQMHistogramCheck(const edm::ParameterSet&);
  void dqmEndRun(DQMStore::IBooker&, DQMStore::IGetter&, edm::Run const&, edm::EventSetup const&) override;
  void dqmEndJob(DQMStore::IBooker&, DQMStore::IGetter&) override {}

private:
  struct Bound {
    std::string path;
    double minEntries, minMean, maxMean;
  };
  std::vector<Bound> bounds_;
};

DQMHistogramCheck::DQMHistogramCheck(const edm::ParameterSet& ps) {
  for (const auto& h : ps.getParameter<std::vector<edm::ParameterSet>>("histograms"))
    bounds_.push_back({h.getParameter<std::string>("path"),
                       h.getParameter<double>("minEntries"),
                       h.getParameter<double>("minMean"),
                       h.getParameter<double>("maxMean")});
}

void DQMHistogramCheck::dqmEndRun(DQMStore::IBooker&,
                                  DQMStore::IGetter& getter,
                                  edm::Run const&,
                                  edm::EventSetup const&) {
  // check them all before failing, so one run shows every value
  std::vector<std::string> failures;
  for (const auto& b : bounds_) {
    const auto* me = getter.get(b.path);
    if (!me) {
      failures.push_back("no " + b.path + " in the DQM store");
      continue;
    }
    const double entries = me->getEntries(), mean = me->getMean();
    edm::LogPrint("DQMHistogramCheck") << b.path << ": " << entries << " entries, mean " << mean;
    if (entries < b.minEntries)
      failures.push_back(b.path + ": " + std::to_string(entries) + " entries, fewer than " +
                         std::to_string(b.minEntries));
    else if (mean < b.minMean || mean > b.maxMean)
      failures.push_back(b.path + ": mean " + std::to_string(mean) + " outside [" + std::to_string(b.minMean) +
                         ", " + std::to_string(b.maxMean) + "]");
  }
  if (!failures.empty()) {
    cms::Exception e("DQMHistogramCheck");
    for (const auto& f : failures)
      e << f << "\n";
    throw e;
  }
}

DEFINE_FWK_MODULE(DQMHistogramCheck);
