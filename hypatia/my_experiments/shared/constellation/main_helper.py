# The MIT License (MIT)
#
# Copyright (c) 2020 ETH Zurich
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
SHARED_DIR = CURRENT_DIR.parent
HYPATIA_DIR = SHARED_DIR.parent.parent
SATGENPY_DIR = HYPATIA_DIR / "satgenpy"
INPUT_DATA_DIR = SHARED_DIR / "input_data"

if str(SATGENPY_DIR) not in sys.path:
    sys.path.insert(0, str(SATGENPY_DIR))

import satgen
from astropy import units as u


class MainHelper:

    def __init__(
            self,
            BASE_NAME,
            NICE_NAME,
            ECCENTRICITY,
            ARG_OF_PERIGEE_DEGREE,
            PHASE_DIFF,
            MEAN_MOTION_REV_PER_DAY,
            ALTITUDE_M,
            MAX_GSL_LENGTH_M,
            MAX_ISL_LENGTH_M,
            NUM_ORBS,
            NUM_SATS_PER_ORB,
            INCLINATION_DEGREE,
    ):
        self.BASE_NAME = BASE_NAME
        self.NICE_NAME = NICE_NAME
        self.ECCENTRICITY = ECCENTRICITY
        self.ARG_OF_PERIGEE_DEGREE = ARG_OF_PERIGEE_DEGREE
        self.PHASE_DIFF = PHASE_DIFF
        self.MEAN_MOTION_REV_PER_DAY = MEAN_MOTION_REV_PER_DAY
        self.ALTITUDE_M = ALTITUDE_M
        self.MAX_GSL_LENGTH_M = MAX_GSL_LENGTH_M
        self.MAX_ISL_LENGTH_M = MAX_ISL_LENGTH_M
        self.NUM_ORBS = NUM_ORBS
        self.NUM_SATS_PER_ORB = NUM_SATS_PER_ORB
        self.INCLINATION_DEGREE = INCLINATION_DEGREE

    def calculate(
            self,
            output_generated_data_dir,      # Final directory in which the result will be placed
            duration_s,
            time_step_ms,
            isl_selection,            # isls_{none, plus_grid}
            gs_selection,             # ground_stations_{top_100, paris_moscow_grid}
            dynamic_state_algorithm,  # algorithm_{free_one_only_{gs_relays,_over_isls}, paired_many_only_over_isls}
            num_threads
    ):

        output_generated_data_dir = Path(output_generated_data_dir)

        # Add base name to setting
        name = self.BASE_NAME + "_" + isl_selection + "_" + gs_selection + "_" + dynamic_state_algorithm
        experiment_dir = output_generated_data_dir / name

        # Create output directories
        output_generated_data_dir.mkdir(parents=True, exist_ok=True)
        experiment_dir.mkdir(parents=True, exist_ok=True)

        # Ground stations
        print("Generating ground stations...")
        if gs_selection == "ground_stations_top_100":
            satgen.extend_ground_stations(
                str(INPUT_DATA_DIR / "ground_stations_top_100.basic.txt"),
                str(experiment_dir / "ground_stations.txt")
            )
        elif gs_selection == "ground_stations_top_50":
            satgen.extend_ground_stations(
                str(INPUT_DATA_DIR / "ground_stations_top_50.basic.txt"),
                str(experiment_dir / "ground_stations.txt")
            )
        elif gs_selection == "ground_stations_paris_moscow_grid":
            satgen.extend_ground_stations(
                str(INPUT_DATA_DIR / "ground_stations_paris_moscow_grid.basic.txt"),
                str(experiment_dir / "ground_stations.txt")
            )
        elif gs_selection == "ground_stations_iridium_6_gateways":
            satgen.extend_ground_stations(
                str(INPUT_DATA_DIR / "ground_stations_iridium_6_gateways.basic.txt"),
                str(experiment_dir / "ground_stations.txt")
            )
        else:
            raise ValueError("Unknown ground station selection: " + gs_selection)

        # TLEs
        print("Generating TLEs...")
        satgen.generate_tles_from_scratch_manual(
            str(experiment_dir / "tles.txt"),
            self.NICE_NAME,
            self.NUM_ORBS,
            self.NUM_SATS_PER_ORB,
            self.PHASE_DIFF,
            self.INCLINATION_DEGREE,
            self.ECCENTRICITY,
            self.ARG_OF_PERIGEE_DEGREE,
            self.MEAN_MOTION_REV_PER_DAY
        )

        # ISLs
        print("Generating ISLs...")
        if isl_selection == "isls_plus_grid":
            # Choose an isl_shift that matches the phasing of the Walker constellation.
            # For many small-per-orbit constellations (like Iridium 11), connecting the
            # same-index satellite in the adjacent orbit can exceed the physical ISL
            # maximum. Using roughly half the satellites per orbit as a shift tends to
            # produce nearer neighbors across adjacent planes.
            isl_shift = int(self.NUM_SATS_PER_ORB / 2)
            satgen.generate_plus_grid_isls(
                str(experiment_dir / "isls.txt"),
                self.NUM_ORBS,
                self.NUM_SATS_PER_ORB,
                isl_shift=isl_shift,
                idx_offset=0
            )
            # Post-filter generated ISLs to ensure they never exceed the allowed max ISL
            # length during the simulation window. Some Walker phasings (small sats/orbit)
            # produce long cross-plane links that are not physically valid.
            try:
                # Read generated ISLs
                isls_path = experiment_dir / "isls.txt"
                list_isls = satgen.read_isls(str(isls_path), self.NUM_ORBS * self.NUM_SATS_PER_ORB)

                # Read TLEs to access epoch and satellite objects
                tles = satgen.read_tles(str(experiment_dir / "tles.txt"))
                epoch = tles["epoch"]
                satellites = tles["satellites"]

                # Sampling: check up to 500 evenly spaced instants across duration
                sample_count = min(500, max(10, int(duration_s)))
                times_ns = [int(i * (duration_s * 1e9) / float(sample_count - 1)) for i in range(sample_count)]

                filtered_isls = []
                for (a, b) in list_isls:
                    valid = True
                    for t_ns in times_ns:
                        try:
                            time = epoch + t_ns * u.ns
                            sat_distance_m = satgen.distance_m_between_satellites(
                                satellites[a], satellites[b], str(epoch), str(time)
                            )
                        except Exception:
                            # If distance computation fails for some instant, treat as invalid
                            valid = False
                            break
                        if sat_distance_m > self.MAX_ISL_LENGTH_M:
                            valid = False
                            break
                    if valid:
                        filtered_isls.append((a, b))

                # Overwrite isls.txt with filtered list
                with open(isls_path, 'w+') as f:
                    for (a, b) in filtered_isls:
                        f.write(str(a) + " " + str(b) + "\n")

                print("Filtered ISLs: kept %d of %d" % (len(filtered_isls), len(list_isls)))
            except Exception as e:
                print("Warning: ISL post-filtering failed: " + str(e))
        elif isl_selection == "isls_none":
            satgen.generate_empty_isls(
                str(experiment_dir / "isls.txt")
            )
        else:
            raise ValueError("Unknown ISL selection: " + isl_selection)

        # Description
        print("Generating description...")
        satgen.generate_description(
            str(experiment_dir / "description.txt"),
            self.MAX_GSL_LENGTH_M,
            self.MAX_ISL_LENGTH_M
        )

        # GSL interfaces
        ground_stations = satgen.read_ground_stations_extended(
            str(experiment_dir / "ground_stations.txt")
        )
        if dynamic_state_algorithm == "algorithm_free_one_only_gs_relays" \
                or dynamic_state_algorithm == "algorithm_free_one_only_over_isls":
            gsl_interfaces_per_satellite = 1
        elif dynamic_state_algorithm == "algorithm_paired_many_only_over_isls":
            gsl_interfaces_per_satellite = len(ground_stations)
        else:
            raise ValueError("Unknown dynamic state algorithm: " + dynamic_state_algorithm)

        print("Generating GSL interfaces info..")
        satgen.generate_simple_gsl_interfaces_info(
            str(experiment_dir / "gsl_interfaces_info.txt"),
            self.NUM_ORBS * self.NUM_SATS_PER_ORB,
            len(ground_stations),
            gsl_interfaces_per_satellite,  # GSL interfaces per satellite
            1,  # (GSL) Interfaces per ground station
            1,  # Aggregate max. bandwidth satellite (unit unspecified)
            1   # Aggregate max. bandwidth ground station (same unspecified unit)
        )

        # Forwarding state
        print("Generating forwarding state...")
        satgen.help_dynamic_state(
            str(output_generated_data_dir),
            num_threads,  # Number of threads
            name,
            time_step_ms,
            duration_s,
            self.MAX_GSL_LENGTH_M,
            self.MAX_ISL_LENGTH_M,
            dynamic_state_algorithm,
            True
        )
