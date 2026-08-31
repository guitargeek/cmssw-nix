// Read a BeamSpotObjects payload out of the EventSetup and check it against
// the values the writer put in.
//
// Nothing here knows the payload came from sqlite: the module just asks the
// EventSetup for a record. That indirection is the point - if this passes,
// PoolDBESSource resolved a tag, coral opened the database, and the payload
// deserialized, all through the ordinary conditions path a real job uses.

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/ESHandle.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Utilities/interface/ESGetToken.h"
#include "FWCore/Utilities/interface/Exception.h"

#include "CondFormats/BeamSpotObjects/interface/BeamSpotObjects.h"
#include "CondFormats/DataRecord/interface/BeamSpotObjectsRcd.h"

#include <cmath>
#include <iostream>

// The accessors were renamed between the two releases (GetX -> x). The
// EventSetup access was not: the token form below is the modern one and
// works in both, unlike the legacy setup.get<Record>().get(handle), which
// 20_1 no longer has.
#ifdef CMSSW_10_6_ERA
#define BS_X GetX
#define BS_Y GetY
#define BS_Z GetZ
#define BS_SIGMAZ GetSigmaZ
#define BS_XERROR GetXError
#else
#define BS_X x
#define BS_Y y
#define BS_Z z
#define BS_SIGMAZ sigmaZ
#define BS_XERROR xError
#endif

class BeamSpotDBReader : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit BeamSpotDBReader(const edm::ParameterSet& ps)
      : token_(esConsumes<BeamSpotObjects, BeamSpotObjectsRcd>()),
        x_(ps.getParameter<double>("expectedX")),
        y_(ps.getParameter<double>("expectedY")),
        z_(ps.getParameter<double>("expectedZ")),
        sigmaZ_(ps.getParameter<double>("expectedSigmaZ")),
        tolerance_(ps.getParameter<double>("tolerance")) {}

private:
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;
  void check(const char* what, double got, double expected) const;

  const edm::ESGetToken<BeamSpotObjects, BeamSpotObjectsRcd> token_;
  const double x_, y_, z_, sigmaZ_, tolerance_;
  unsigned int seen_ = 0;
};

void BeamSpotDBReader::check(const char* what, double got, double expected) const {
  if (std::abs(got - expected) > tolerance_) {
    throw cms::Exception("PayloadMismatch")
        << what << " read back as " << got << ", expected " << expected;
  }
}

void BeamSpotDBReader::analyze(const edm::Event& event, const edm::EventSetup& setup) {
  const BeamSpotObjects& bs = setup.getData(token_);
  check("x", bs.BS_X(), x_);
  check("y", bs.BS_Y(), y_);
  check("z", bs.BS_Z(), z_);
  check("sigmaZ", bs.BS_SIGMAZ(), sigmaZ_);

  ++seen_;
  std::cout << "run " << event.id().run() << " event " << event.id().event() << ": beam spot ("
            << bs.BS_X() << ", " << bs.BS_Y() << ", " << bs.BS_Z() << "), sigmaZ = " << bs.BS_SIGMAZ()
            << ", xError = " << bs.BS_XERROR() << std::endl;
}

void BeamSpotDBReader::endJob() {
  if (seen_ == 0) {
    throw cms::Exception("NoEvents") << "the payload was never read - the job saw no events";
  }
  std::cout << "beam spot payload verified in " << seen_ << " events" << std::endl;
}

DEFINE_FWK_MODULE(BeamSpotDBReader);
