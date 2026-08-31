// Write a BeamSpotObjects payload into a local sqlite conditions database
// through PoolDBOutputService.
//
// The values are deliberately unround so that reading them back proves the
// payload really made the round trip through coral's sqlite backend and the
// boost serialization in CondFormats, rather than a default-constructed
// object happening to match.

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "FWCore/Utilities/interface/Exception.h"

#include "CondCore/DBOutputService/interface/PoolDBOutputService.h"
#include "CondFormats/BeamSpotObjects/interface/BeamSpotObjects.h"

#include <iostream>

// The two releases disagree about the names of everything this module
// touches. CMSSW_10_6_ERA is defined by CMakeLists.txt for the old release;
// the modern spellings are the default.
//
//   BeamSpotObjects   SetPosition/SetSigmaZ/SetType/SetCovariance
//                  -> setPosition/setSigmaZ/setType/setCovariance
//   PoolDBOutputService  writeOne(T*, ...) -> writeOneIOV(const T&, ...)
//
// The rename is not cosmetic in the second case: the old signature took a
// pointer and the new one takes a const reference, so the ownership question
// the old comment here had to answer ("writeOne copies the payload, so the
// stack object is fine") no longer arises.
#ifdef CMSSW_10_6_ERA
#define BS_SET_POSITION SetPosition
#define BS_SET_SIGMAZ SetSigmaZ
#define BS_SET_TYPE SetType
#define BS_SET_COVARIANCE SetCovariance
#define BS_WRITE_ONE(db, payload, time, record) db->writeOne(&(payload), time, record)
#else
#define BS_SET_POSITION setPosition
#define BS_SET_SIGMAZ setSigmaZ
#define BS_SET_TYPE setType
#define BS_SET_COVARIANCE setCovariance
#define BS_WRITE_ONE(db, payload, time, record) db->writeOneIOV(payload, time, record)
#endif

class BeamSpotDBWriter : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit BeamSpotDBWriter(const edm::ParameterSet& ps)
      : record_(ps.getParameter<std::string>("record")),
        x_(ps.getParameter<double>("x")),
        y_(ps.getParameter<double>("y")),
        z_(ps.getParameter<double>("z")),
        sigmaZ_(ps.getParameter<double>("sigmaZ")) {}

private:
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;

  const std::string record_;
  const double x_, y_, z_, sigmaZ_;
  bool written_ = false;
};

void BeamSpotDBWriter::analyze(const edm::Event& event, const edm::EventSetup&) {
  if (written_)
    return;

  BeamSpotObjects payload;
  payload.BS_SET_POSITION(x_, y_, z_);
  payload.BS_SET_SIGMAZ(sigmaZ_);
  payload.BS_SET_TYPE(1);
  // a diagonal covariance, so the error accessors have something to take the
  // square root of on the way back
  for (int i = 0; i < 7; ++i) {
    payload.BS_SET_COVARIANCE(i, i, 1e-4);
  }

  edm::Service<cond::service::PoolDBOutputService> db;
  if (!db.isAvailable()) {
    throw cms::Exception("Configuration") << "PoolDBOutputService is not configured";
  }

  // The service copies the payload; the stack object above is fine.
  BS_WRITE_ONE(db, payload, db->beginOfTime(), record_);
  written_ = true;

  std::cout << "wrote " << record_ << " for run " << event.id().run() << ": "
            << "x = " << x_ << ", y = " << y_ << ", z = " << z_ << ", sigmaZ = " << sigmaZ_ << std::endl;
}

void BeamSpotDBWriter::endJob() {
  if (!written_) {
    throw cms::Exception("NoPayload") << "no payload was written - the job saw no events";
  }
}

DEFINE_FWK_MODULE(BeamSpotDBWriter);
