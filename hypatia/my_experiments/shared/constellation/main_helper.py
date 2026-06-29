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
            num_threads,
            ground_stations_basic_file=None,
            isl_shift=None,
            dynamic_state_config=None
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
        if ground_stations_basic_file is not None:
            satgen.extend_ground_stations(
                str(ground_stations_basic_file),
                str(experiment_dir / "ground_stations.txt")
            )
        elif gs_selection == "ground_stations_top_100":
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
            if isl_shift is None:
                isl_shift = 0
            isl_shift = int(isl_shift)
            if isl_shift < 0 or isl_shift >= self.NUM_SATS_PER_ORB:
                raise ValueError(
                    "isl_shift must be in [0, %d], got %d"
                    % (self.NUM_SATS_PER_ORB - 1, isl_shift)
                )
            print("Using ISL shift: %d" % isl_shift)
            satgen.generate_plus_grid_isls(
                str(experiment_dir / "isls.txt"),
                self.NUM_ORBS,
                self.NUM_SATS_PER_ORB,
                isl_shift=isl_shift,
                idx_offset=0
            )
            # Keep the full plus-grid candidate set in isls.txt. Dynamic-state
            # generation decides at each time step which candidates are within
            # max range, which is necessary for intermittent cross-plane ISLs.
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
        elif dynamic_state_algorithm == "algorithm_free_gs_one_sat_many_only_over_isls" \
                or dynamic_state_algorithm == "algorithm_paired_many_only_over_isls":
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
            True,
            dynamic_state_config
        )
