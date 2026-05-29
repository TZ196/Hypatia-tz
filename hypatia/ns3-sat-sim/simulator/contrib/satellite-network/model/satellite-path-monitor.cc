/*
 * Track path-level satellite traffic matrices.
 */

#include "satellite-path-monitor.h"

#include <algorithm>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>

#include "ns3/exp-util.h"
#include "ns3/log.h"
#include "ns3/simulator.h"

namespace ns3 {

NS_LOG_COMPONENT_DEFINE ("SatellitePathMonitor");

bool SatellitePathMonitor::s_enabled = false;
uint32_t SatellitePathMonitor::s_numSatellites = 0;
int64_t SatellitePathMonitor::s_intervalNs = 0;
uint64_t SatellitePathMonitor::s_numTimeBins = 0;
std::string SatellitePathMonitor::s_logsDir = "";
uint64_t SatellitePathMonitor::s_maxPathLengthSeen = 0;
uint64_t SatellitePathMonitor::s_islTransmitEvents = 0;
uint64_t SatellitePathMonitor::s_transitPairObservations = 0;
uint64_t SatellitePathMonitor::s_nonAdjacentPairObservations = 0;
uint64_t SatellitePathMonitor::s_nonAdjacentBytes = 0;
std::unordered_map<uint64_t, std::vector<uint32_t> > SatellitePathMonitor::s_packetSatellites;
std::vector<uint64_t> SatellitePathMonitor::s_pathLengthHistogram;
std::map<uint64_t, SatellitePathMonitor::Counter> SatellitePathMonitor::s_counters;

void
SatellitePathMonitor::Initialize (
    bool enabled,
    uint32_t numSatellites,
    int64_t intervalNs,
    int64_t simulationEndTimeNs,
    const std::string& logsDir)
{
  s_enabled = enabled;
  s_numSatellites = numSatellites;
  s_intervalNs = intervalNs;
  s_logsDir = logsDir;
  s_maxPathLengthSeen = 0;
  s_islTransmitEvents = 0;
  s_transitPairObservations = 0;
  s_nonAdjacentPairObservations = 0;
  s_nonAdjacentBytes = 0;
  s_packetSatellites.clear ();
  s_pathLengthHistogram.clear ();
  s_counters.clear ();

  if (!s_enabled)
    {
      s_numTimeBins = 0;
      return;
    }

  NS_ABORT_MSG_IF (s_numSatellites == 0, "Satellite path monitor needs at least one satellite");
  NS_ABORT_MSG_IF (s_intervalNs <= 0, "satellite_path_tracking_interval_ns must be positive");
  NS_ABORT_MSG_IF (simulationEndTimeNs <= 0, "simulation_end_time_ns must be positive");

  s_numTimeBins = (simulationEndTimeNs + s_intervalNs - 1) / s_intervalNs;
  s_pathLengthHistogram = std::vector<uint64_t> (s_numSatellites + 1, 0);
  std::cout << "  > Satellite path tracking.. enabled, interval " << s_intervalNs
            << " ns, bins " << s_numTimeBins << std::endl;
}

bool
SatellitePathMonitor::IsEnabled (void)
{
  return s_enabled;
}

bool
SatellitePathMonitor::IsSatelliteNode (uint32_t nodeId)
{
  return s_enabled && nodeId < s_numSatellites;
}

void
SatellitePathMonitor::RecordIslTransmit (
    Ptr<const Packet> packet,
    uint32_t fromSatelliteId,
    uint32_t toSatelliteId,
    uint64_t bytes)
{
  if (!IsSatelliteNode (fromSatelliteId) || !IsSatelliteNode (toSatelliteId) || fromSatelliteId == toSatelliteId)
    {
      return;
    }

  uint64_t packetKey = PacketKey (packet);
  std::vector<uint32_t>& path = s_packetSatellites[packetKey];
  s_islTransmitEvents += 1;

  if (std::find (path.begin (), path.end (), fromSatelliteId) == path.end ())
    {
      path.push_back (fromSatelliteId);
      ObservePathLength (path.size ());
    }

  // Attribute this transmitted packet to every earlier satellite on its path.
  // For A->B->C, the B->C transmission contributes once to A->C and once to B->C.
  for (uint32_t pathIndex = 0; pathIndex < path.size (); pathIndex++)
    {
      uint32_t fromSat = path[pathIndex];
      if (fromSat != toSatelliteId)
        {
          Increment (fromSat, toSatelliteId, bytes, false);
          s_transitPairObservations += 1;
          if (fromSat != fromSatelliteId)
            {
              s_nonAdjacentPairObservations += 1;
              s_nonAdjacentBytes += bytes;
            }
        }
    }

  if (std::find (path.begin (), path.end (), toSatelliteId) == path.end ())
    {
      path.push_back (toSatelliteId);
      ObservePathLength (path.size ());
    }
}

void
SatellitePathMonitor::RecordSatelliteDrop (Ptr<Packet> packet, uint32_t satelliteId, uint64_t bytes)
{
  if (!IsSatelliteNode (satelliteId))
    {
      return;
    }

  uint64_t packetKey = PacketKey (packet);
  auto it = s_packetSatellites.find (packetKey);
  if (it == s_packetSatellites.end ())
    {
      return;
    }

  for (uint32_t fromSat : it->second)
    {
      if (fromSat != satelliteId)
        {
          Increment (fromSat, satelliteId, bytes, true);
        }
    }

  s_packetSatellites.erase (it);
}

void
SatellitePathMonitor::RecordGroundStationReceive (Ptr<Packet> packet)
{
  if (!s_enabled)
    {
      return;
    }
  EndPathIfPresent (packet);
}

uint64_t
SatellitePathMonitor::PacketKey (Ptr<const Packet> packet)
{
  return packet->GetUid ();
}

void
SatellitePathMonitor::EndPathIfPresent (Ptr<Packet> packet)
{
  s_packetSatellites.erase (PacketKey (packet));
}

void
SatellitePathMonitor::ObservePathLength (uint64_t pathLength)
{
  if (pathLength > s_maxPathLengthSeen)
    {
      s_maxPathLengthSeen = pathLength;
    }
  if (pathLength < s_pathLengthHistogram.size ())
    {
      s_pathLengthHistogram[pathLength] += 1;
    }
}

void
SatellitePathMonitor::Increment (uint32_t fromSat, uint32_t toSat, uint64_t bytes, bool isDrop)
{
  if (fromSat >= s_numSatellites || toSat >= s_numSatellites || fromSat == toSat)
    {
      return;
    }

  uint64_t timeBin = CurrentTimeBin ();
  if (timeBin >= s_numTimeBins)
    {
      return;
    }

  Counter& counter = s_counters[MatrixKey (timeBin, fromSat, toSat)];
  if (isDrop)
    {
      counter.dropBytes += bytes;
      counter.dropPackets += 1;
    }
  else
    {
      counter.bytes += bytes;
      counter.packets += 1;
    }
}

uint64_t
SatellitePathMonitor::CurrentTimeBin (void)
{
  int64_t nowNs = Simulator::Now ().GetNanoSeconds ();
  if (nowNs <= 0)
    {
      return 0;
    }
  return nowNs / s_intervalNs;
}

uint64_t
SatellitePathMonitor::MatrixKey (uint64_t timeBin, uint32_t fromSat, uint32_t toSat)
{
  return (timeBin * s_numSatellites + fromSat) * s_numSatellites + toSat;
}

void
SatellitePathMonitor::WriteCsvMatrices (void)
{
  if (!s_enabled)
    {
      return;
    }

  std::string baseDir = s_logsDir + "/sat_path_flow";
  std::string bytesDir = baseDir + "/bytes";
  std::string packetsDir = baseDir + "/packets";
  std::string dropBytesDir = baseDir + "/drop_bytes";
  std::string dropPacketsDir = baseDir + "/drop_packets";

  mkdir_if_not_exists (baseDir);
  mkdir_if_not_exists (bytesDir);
  mkdir_if_not_exists (packetsDir);
  mkdir_if_not_exists (dropBytesDir);
  mkdir_if_not_exists (dropPacketsDir);

  std::ofstream metadata (baseDir + "/metadata.txt");
  NS_ABORT_MSG_IF (!metadata.is_open (), "Could not open satellite path monitor metadata file");
  metadata << "num_satellites=" << s_numSatellites << std::endl;
  metadata << "num_time_bins=" << s_numTimeBins << std::endl;
  metadata << "interval_ns=" << s_intervalNs << std::endl;
  metadata << "layout=matrix[from_sat][to_sat]" << std::endl;
  metadata << "tracking_key=packet_uid" << std::endl;
  metadata << "tracking_point=isl_transmit" << std::endl;
  metadata << "max_path_length_seen=" << s_maxPathLengthSeen << std::endl;
  metadata << "isl_transmit_events=" << s_islTransmitEvents << std::endl;
  metadata << "transit_pair_observations=" << s_transitPairObservations << std::endl;
  metadata << "non_adjacent_pair_observations=" << s_nonAdjacentPairObservations << std::endl;
  metadata << "non_adjacent_bytes=" << s_nonAdjacentBytes << std::endl;
  metadata << "open_packet_paths_at_finish=" << s_packetSatellites.size () << std::endl;
  WritePathLengthHistogram (metadata);
  metadata.close ();

  uint64_t matrixSize = static_cast<uint64_t> (s_numSatellites) * s_numSatellites;
  for (uint64_t t = 0; t < s_numTimeBins; t++)
    {
      std::vector<uint64_t> bytes (matrixSize, 0);
      std::vector<uint64_t> packets (matrixSize, 0);
      std::vector<uint64_t> dropBytes (matrixSize, 0);
      std::vector<uint64_t> dropPackets (matrixSize, 0);

      uint64_t firstKey = MatrixKey (t, 0, 0);
      uint64_t endKey = firstKey + matrixSize;
      for (auto it = s_counters.lower_bound (firstKey);
           it != s_counters.end () && it->first < endKey;
           ++it)
        {
          uint64_t matrixIndex = it->first - firstKey;
          bytes[matrixIndex] = it->second.bytes;
          packets[matrixIndex] = it->second.packets;
          dropBytes[matrixIndex] = it->second.dropBytes;
          dropPackets[matrixIndex] = it->second.dropPackets;
        }

      std::ostringstream filename;
      filename << "t_" << std::setw (6) << std::setfill ('0') << t << ".csv";
      WriteMetricMatrix (bytesDir, filename.str (), bytes);
      WriteMetricMatrix (packetsDir, filename.str (), packets);
      WriteMetricMatrix (dropBytesDir, filename.str (), dropBytes);
      WriteMetricMatrix (dropPacketsDir, filename.str (), dropPackets);
    }
}

void
SatellitePathMonitor::WriteMetricMatrix (
    const std::string& dir,
    const std::string& filename,
    const std::vector<uint64_t>& values)
{
  std::ofstream fs (dir + "/" + filename);
  NS_ABORT_MSG_IF (!fs.is_open (), "Could not open satellite path monitor matrix file");
  for (uint32_t row = 0; row < s_numSatellites; row++)
    {
      for (uint32_t col = 0; col < s_numSatellites; col++)
        {
          if (col > 0)
            {
              fs << ",";
            }
          fs << values[static_cast<uint64_t> (row) * s_numSatellites + col];
        }
      fs << std::endl;
    }
  fs.close ();
}

void
SatellitePathMonitor::WritePathLengthHistogram (std::ostream& metadata)
{
  metadata << "path_length_histogram=";
  bool first = true;
  for (uint32_t pathLength = 1; pathLength < s_pathLengthHistogram.size (); pathLength++)
    {
      uint64_t count = s_pathLengthHistogram[pathLength];
      if (count == 0)
        {
          continue;
        }
      if (!first)
        {
          metadata << ",";
        }
      metadata << pathLength << ":" << count;
      first = false;
    }
  metadata << std::endl;
}

} // namespace ns3
