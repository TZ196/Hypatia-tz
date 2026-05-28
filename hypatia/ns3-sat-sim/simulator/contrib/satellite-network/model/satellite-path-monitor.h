/*
 * Track path-level satellite traffic matrices.
 */

#ifndef SATELLITE_PATH_MONITOR_H
#define SATELLITE_PATH_MONITOR_H

#include <cstdint>
#include <map>
#include <ostream>
#include <string>
#include <unordered_map>
#include <vector>

#include "ns3/packet.h"
#include "ns3/ptr.h"
#include "ns3/tag.h"
#include "ns3/type-id.h"

namespace ns3 {

class SatellitePathPacketTag : public Tag
{
public:
  static TypeId GetTypeId (void);
  virtual TypeId GetInstanceTypeId (void) const;
  virtual uint32_t GetSerializedSize (void) const;
  virtual void Serialize (TagBuffer i) const;
  virtual void Deserialize (TagBuffer i);
  virtual void Print (std::ostream &os) const;

  void SetPathId (uint64_t pathId);
  uint64_t GetPathId (void) const;

private:
  uint64_t m_pathId = 0;
};

class SatellitePathMonitor
{
public:
  static void Initialize (
      bool enabled,
      uint32_t numSatellites,
      int64_t intervalNs,
      int64_t simulationEndTimeNs,
      const std::string& logsDir);

  static bool IsEnabled (void);
  static bool IsSatelliteNode (uint32_t nodeId);
  static void RecordSatelliteReceive (Ptr<Packet> packet, uint32_t satelliteId, uint64_t bytes);
  static void RecordSatelliteDrop (Ptr<Packet> packet, uint32_t satelliteId, uint64_t bytes);
  static void RecordGroundStationReceive (Ptr<Packet> packet);
  static void WriteCsvMatrices (void);

private:
  struct Counter
  {
    uint64_t bytes = 0;
    uint64_t packets = 0;
    uint64_t dropBytes = 0;
    uint64_t dropPackets = 0;
  };

  static uint64_t EnsurePathId (Ptr<Packet> packet);
  static bool GetPathId (Ptr<Packet> packet, uint64_t& pathId);
  static void EndPathIfPresent (Ptr<Packet> packet);
  static void Increment (uint32_t fromSat, uint32_t toSat, uint64_t bytes, bool isDrop);
  static uint64_t CurrentTimeBin (void);
  static uint64_t MatrixKey (uint64_t timeBin, uint32_t fromSat, uint32_t toSat);
  static void WriteMetricMatrix (
      const std::string& dir,
      const std::string& filename,
      const std::vector<uint64_t>& values);

  static bool s_enabled;
  static uint32_t s_numSatellites;
  static int64_t s_intervalNs;
  static uint64_t s_numTimeBins;
  static std::string s_logsDir;
  static uint64_t s_nextPathId;
  static std::unordered_map<uint64_t, std::vector<uint32_t> > s_pathSatellites;
  static std::map<uint64_t, Counter> s_counters;
};

} // namespace ns3

#endif // SATELLITE_PATH_MONITOR_H
