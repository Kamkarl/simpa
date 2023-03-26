# SPDX-FileCopyrightText: 2021 Division of Intelligent Medical Systems, DKFZ
# SPDX-FileCopyrightText: 2021 Janek Groehl
# SPDX-License-Identifier: MIT

import numpy as np
from simpa.utils import Tags
from simpa.log import Logger
from simpa.io_handling import load_data_field, save_data_field
from simpa.core.processing_components import ProcessingComponent
from simpa.utils.quality_assurance.data_sanity_testing import assert_array_well_defined
from simpa.core.simulation_modules.reconstruction_module.reconstruction_utils import tukey_bandpass_filtering_with_settings, get_reconstruction_time_step_window, compute_image_dimensions, preparing_reconstruction_and_obtaining_reconstruction_settings
from simpa.core.device_digital_twins.digital_device_twin_base import DigitalDeviceTwinBase

import matplotlib.pyplot as plt # TODO: Delete if debug plot is removed


class AddNoisyTimeSeries(ProcessingComponent):
    """
    Operations:
        - Bandpassfilter simulated time series
        - Load noisy in-aqua time series data
        - Bandpassfilter noisy in-aqua data (if needed, per default not needed)
        - Crop noisy in-aqua data (if needed, per default not needed)
        - Scale noisy in-aqua data with Tags.SCALING_FACTOR
        - Take broken sensors into account by setting simulated time series data of corresponding sensors to 0
        - Add noisy in-aqua data to simulated data in the window relevant for the FOV
        - Perform laser energy correction (if specified)

    Component Settings:
       Tags.IN_AQUA_DATA_PATH: path of in-aqua time series data
       Tags.IN_AQUA_DATA: np.ndarray containing additive noise to be added on simulated signal
       Tags.BROKEN_SENSORS: (for example: np.array([30,94,145, 247]))
       Tags.SCALING_FACTOR: scaling factor of the noise data added to the signal: Signal + Scaling_Factor * Noise
       Tags.LASER_ENERGY_CORRECTION: whether to perform laser energy correction
       Tags.IN_AQUA_LASER_ENERGY_IN_MILLIJOULE: laser energy of the corresponding waterbath measurement in mJ
        Tags.RECONSTRUCTION_TIME_STEPS: specify which time steps are used for the reconstruction and should be covered with noise
        Tags.BANDPASS_FILTERED_IN_AQUA_DATA: whether loaded in-aqua data is already bandpassfiltered, default True
        Tags.CROPPED_IN_AQUA_DATA: is loaded in-aqua data already cropped, default True
    """

    def __init__(self, global_settings, component_settings_key: str, debug_plot: bool = False):
        super(AddNoisyTimeSeries, self).__init__(global_settings=global_settings, component_settings_key=component_settings_key)
        self.debug_plot = debug_plot
      
    def check_input(self, time_series_data: np.ndarray):
        (n_sensors, _) = time_series_data.shape

        if Tags.SCALING_FACTOR not in self.component_settings:
            self.logger.debug("Tags.SCALING_FACTOR was not set. Thus, it is set to 1.")
            self.component_settings[Tags.SCALING_FACTOR] = 1
        else: 
            if self.component_settings[Tags.SCALING_FACTOR] is None:
                self.logger.debug("Tags.SCALING_FACTOR was not set. Thus, it is set to 1.")
                self.component_settings[Tags.SCALING_FACTOR] = 1
            
        if Tags.LASER_ENERGY_CORRECTION in self.component_settings and self.component_settings[Tags.LASER_ENERGY_CORRECTION]:
            if Tags.IN_AQUA_LASER_ENERGY_IN_MILLIJOULE not in self.component_settings:
                self.logger.error("Tags.IN_AQUA_LASER_ENERGY_IN_MILLIJOULE has to be\
                                  set if Tags.LASER_ENERGY_CORRECTION is True")
        
        # create indicator function for non-broken sensors
        self.working_sensors = np.ones(n_sensors)
        if Tags.BROKEN_SENSORS in self.component_settings and len(self.component_settings[Tags.BROKEN_SENSORS]) > 0:
            self.working_sensors[self.component_settings[Tags.BROKEN_SENSORS]] = 0 # set to 0 for broken sensors

    def add_noise(self, time_series_data: np.ndarray, noise_data: np.ndarray, scaling_factor: float, device: DigitalDeviceTwinBase) -> np.ndarray:
        assert noise_data.shape[0] == time_series_data.shape[0], "number of sensors do not match between noisy and simulated time series data"
        if noise_data.shape[1] < time_series_data.shape[1]:
            # read out time step window needed for reconstruction if given or compute it if not
            if Tags.RECONSTRUCTION_TIME_STEPS in self.component_settings:
                time_step_start, time_step_end = self.component_settings[Tags.RECONSTRUCTION_TIME_STEPS]
                self.logger.info(f"use given noise-window: ({time_step_start}, {time_step_end})")
            else:
                self.logger.info("compute noise window based on reconstruction")
                logger = Logger()
                detection_geometry = device.get_detection_geometry()
                reconstruction_settings = self.global_settings.get_reconstruction_settings()
                _, sensor_positions, speed_of_sound_in_m_per_s, spacing_in_mm, time_spacing_in_ms, torch_device = preparing_reconstruction_and_obtaining_reconstruction_settings(
                    time_series_data, reconstruction_settings, self.global_settings, detection_geometry, self.logger)
                xdim, zdim, ydim, xdim_start, _, ydim_start, _, zdim_start, _ = compute_image_dimensions(
                                                                                detection_geometry, spacing_in_mm, logger)
                time_step_start, time_step_end = get_reconstruction_time_step_window(time_series_data, sensor_positions, xdim, ydim, zdim,
                                                                                     xdim_start, ydim_start, zdim_start, spacing_in_mm,
                                                                                    speed_of_sound_in_m_per_s, time_spacing_in_ms, logger,
                                                                                    torch_device)
            # compute noise window
            window_len = time_step_end + 1 - time_step_start
            safety_margin_before = round((noise_data.shape[1] - window_len)/2)
            noise_start = time_step_start - safety_margin_before
            noise_end = time_step_start - safety_margin_before + noise_data.shape[1]
            # add noise on time series data in this window 
            time_series_data *= self.working_sensors[:,None] # account for broken sensors
            time_series_data[:,noise_start:noise_end] += scaling_factor * noise_data[:,:]
            self.logger.info(f"Add noise from time step {noise_start} to {noise_end}")
            return time_series_data

        elif noise_data.shape[1] == time_series_data.shape[1]:
            return time_series_data * self.working_sensors[:,None] + scaling_factor * noise_data
        
    def do_laser_energy_correction(self, time_series: np.ndarray) -> np.ndarray:
        """
        Apply laser energy correction
        (will be applied to the time series data after the noise is added)

        :param time_series: time series data to be laser energy corrected
        :type time_series: np.ndarray
        :return: laser energy corrected time series data
        :rtype: np.ndarray
        """
        self.logger.info("Perform Laser Energy Correction of noisened Time Series Data.")
        # load energy specified in optical simulation settings
        optical_settings = self.global_settings.get_optical_settings()
        if Tags.LASER_PULSE_ENERGY_IN_MILLIJOULE in optical_settings:
            sim_energy = [Tags.LASER_PULSE_ENERGY_IN_MILLIJOULE]
        else:
            msg = f"No laser energy was set for optical simulation.\
                Laser Energy Correction is not meaningful for initial pressure map with non pascal but arbitrary units."
            self.logger.critical(msg)
            raise KeyError(msg)
        
        noise_sample_energy = self.component_settings[Tags.IN_AQUA_LASER_ENERGY_IN_MILLIJOULE]
        # check whether component setting and optical simulation setting contradict or not
        if sim_energy != noise_sample_energy:
            self.logger.debug(f"Simulated laser energy in optical settings E={sim_energy:.3f} \
                              do not match with energy of noise sample E={noise_sample_energy:.3f}.")
        # check whether Tags.IN_AQUA_LASER_ENERGY_IN_MILLIJOULE was already used for p0 multlication
        if Tags.MULTIPLY_ENERGY_ON_PRESSURE_SETTINGS in self.global_settings and \
            Tags.IN_AQUA_LASER_ENERGY_IN_MILLIJOULE in self.global_settings[Tags.MULTIPLY_ENERGY_ON_PRESSURE_SETTINGS]:
            energy_p0_factor = self.global_settings[Tags.MULTIPLY_ENERGY_ON_PRESSURE_SETTINGS][Tags.IN_AQUA_LASER_ENERGY_IN_MILLIJOULE]
            assert noise_sample_energy == energy_p0_factor, "Energy used for p0 mulitplication\
                  (self.global_settings[Tags.MULTIPLY_ENERGY_ON_PRESSURE_SETTINGS][Tags.IN_AQUA_LASER_ENERGY_IN_MILLIJOULE]=\
                    {energy_p0_factor:.3f}) does not match with given Tags.IN_AQUA_LASER_ENERGY_IN_MILLIJOULE={noise_sample_energy}"
        else:
            self.logger.debug(f"No Tags.MULTIPLY_ENERGY_ON_PRESSURE_SETTINGS in global settings \
                              or no Tags.IN_AQUA_LASER_ENERGY_IN_MILLIJOULE found in MultiplyEnergy Component.")
        # laser energy correction
        self.logger.info(f"Divide time series by {noise_sample_energy:.3f}mJ")
        time_series /= noise_sample_energy
        return time_series

    def run(self, device) -> None:
        self.logger.info("Adding Device-Specific Noise on Time Series Data...")

        # read out simulated time series data
        wavelength = self.global_settings[Tags.WAVELENGTH]
        time_series_data = load_data_field(self.global_settings[Tags.SIMPA_OUTPUT_PATH], Tags.DATA_FIELD_TIME_SERIES_DATA, wavelength)

        # check which tags are set
        self.check_input(time_series_data)

        # bandpass filter the simulated time series data
        time_series_data = tukey_bandpass_filtering_with_settings(data = time_series_data, global_settings = self.global_settings, 
                                                                  component_settings = self.global_settings.get_reconstruction_settings(),
                                                                  device = device)

        # load noisy in-aqua data 
        if Tags.IN_AQUA_DATA in self.component_settings:
            noise_data = self.component_settings[Tags.IN_AQUA_DATA]
        else:
            self.logger.critical("No in-aqua data was set in AddNoisyTimeSeries Compoment settings.")
            raise("error")

        # preprocess noisy in-aqua data if needed
        if Tags.BANDPASS_FILTERED_IN_AQUA_DATA in self.component_settings:
            if not self.component_settings[Tags.BANDPASS_FILTERED_IN_AQUA_DATA]:
                self.logger.debug("Bandpass filter noisy in-aqua time series data")
                noise_data = tukey_bandpass_filtering_with_settings(data = noise_data, global_settings = self.global_settings, 
                                                                    component_settings = self.component_settings, device = device)
        if Tags.CROPPED_IN_AQUA_DATA in self.component_settings:
            if not self.component_settings[Tags.CROPPED_IN_AQUA_DATA]:
                self.logger.debug("Crop out additive noise in noisy in-aqua time series data.")
                self.logger.critical("Cropping is not implemented yet!")
                pass
        
        if self.debug_plot:
            plt.figure()
            plt.imshow(time_series_data, aspect="auto")
        # add noise components, i.e. broken sensors, sensor offsets, sensor thermal noises
        time_series_data = self.add_noise(time_series_data, noise_data, self.component_settings[Tags.SCALING_FACTOR], device)          
        if self.debug_plot:
            plt.figure()
            plt.imshow(time_series_data, aspect="auto")
            plt.show()

        # laser correct and norm time series data
        if Tags.LASER_ENERGY_CORRECTION in self.component_settings:
            if self.component_settings[Tags.LASER_ENERGY_CORRECTION]:
                self.logger.debug("Laser correct noisened time series data.")
                time_series_data = self.do_laser_energy_correction(time_series_data)

        if not (Tags.IGNORE_QA_ASSERTIONS in self.global_settings and Tags.IGNORE_QA_ASSERTIONS):
            assert_array_well_defined(time_series_data)

        # overwrite the time series data
        save_data_field(time_series_data, self.global_settings[Tags.SIMPA_OUTPUT_PATH], Tags.DATA_FIELD_TIME_SERIES_DATA, wavelength)
        self.logger.info("Adding Device-Specific Noise on Time Series Data...[Done]")