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

namespace ns3 {

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
  static void RecordSatelliteToGroundSend (Ptr<Packet> packet, uint32_t satelliteId, uint64_t bytes);
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

  static bool GetExistingPathId (Ptr<const Packet> packet, uint64_t& pathId);
  static uint64_t GetOrCreatePathId (Ptr<Packet> packet);
  static void EndPathIfPresent (Ptr<Packet> packet);
  static void ObservePathLength (uint64_t pathLength);
  static void Increment (uint32_t fromSat, uint32_t toSat, uint64_t bytes, bool isDrop);
  static void IncrementAtTimeBin (
      uint64_t timeBin,
      uint32_t fromSat,
      uint32_t toSat,
      uint64_t bytes,
      bool isDrop);
  static uint64_t CurrentTimeBin (void);
  static uint64_t MatrixKey (uint64_t timeBin, uint32_t fromSat, uint32_t toSat);
  static void WriteMetricMatrix (
      const std::string& dir,
      const std::string& filename,
      const std::vector<uint64_t>& values);
  static void WritePathLengthHistogram (std::ostream& metadata);

  static bool s_enabled;
  static uint32_t s_numSatellites;
  static int64_t s_intervalNs;
  static uint64_t s_numTimeBins;
  static std::string s_logsDir;
  static uint64_t s_nextPathId;
  static uint64_t s_maxPathLengthSeen;
  static uint64_t s_satelliteReceiveEvents;
  static uint64_t s_pathTagCreations;
  static uint64_t s_singleSatellitePathObservations;
  static uint64_t s_transitPairObservations;
  static uint64_t s_nonAdjacentPairObservations;
  static uint64_t s_nonAdjacentBytes;
  static std::unordered_map<uint64_t, std::vector<uint32_t> > s_pathSatellites;
  static std::unordered_map<uint64_t, uint64_t> s_pathFirstSeenBins;
  static std::vector<uint64_t> s_pathLengthHistogram;
  static std::map<uint64_t, Counter> s_counters;
};

} // namespace ns3

#endif // SATELLITE_PATH_MONITOR_H
