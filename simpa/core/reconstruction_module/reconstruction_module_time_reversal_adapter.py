"""
SPDX-FileCopyrightText: 2021 Computer Assisted Medical Interventions Group, DKFZ
SPDX-FileCopyrightText: 2021 VISION Lab, Cancer Research UK Cambridge Institute (CRUK CI)
SPDX-License-Identifier: MIT
"""

from simpa.utils import Tags, SaveFilePaths
from simpa.utils.settings import Settings
from simpa.core.reconstruction_module import ReconstructionAdapterBase
from simpa.io_handling.io_hdf5 import load_hdf5
import numpy as np
import scipy.io as sio
import subprocess
import os
import inspect


class ReconstructionModuleTimeReversalAdapter(ReconstructionAdapterBase):
    """
    The time reversal adapter includes the time reversal reconstruction
    algorithm implemented by the k-Wave toolkit into SIMPA.

    Time reversal reconstruction uses the time series data and computes the forward simulation model
    backwards in time::

        Treeby, Bradley E., Edward Z. Zhang, and Benjamin T. Cox.
        "Photoacoustic tomography in absorbing acoustic media using
        time reversal." Inverse Problems 26.11 (2010): 115003.


    """

    def get_acoustic_properties(self, input_data: dict, detection_geometry):
        """
        This method extracts the acoustic tissue properties from the settings dictionary and
        amends the information to the input_data.

        :param global_settings: the settings dictionary containing key value pairs with the simulation instructions.
        :param input_data: a dictionary containing the information needed for time reversal.
        """

        tmp_ac_properties = load_hdf5(self.global_settings[Tags.SIMPA_OUTPUT_PATH],
                                      SaveFilePaths.SIMULATION_PROPERTIES.format(Tags.ORIGINAL_DATA,
                                                                                 self.global_settings[Tags.WAVELENGTH]))

        if Tags.ACOUSTIC_SIMULATION_3D not in self.component_settings or not \
                self.component_settings[Tags.ACOUSTIC_SIMULATION_3D]:
            axes = (0, 1)
        else:
            axes = (0, 2)

        pa_device = detection_geometry
        pa_device.check_settings_prerequisites(self.global_settings)
        detector_positions = pa_device.get_detector_element_positions_accounting_for_device_position_mm(self.global_settings)
        detector_positions_voxels = np.round(detector_positions / self.global_settings[Tags.SPACING_MM]).astype(int)

        voxel_spacing = self.global_settings[Tags.SPACING_MM]
        volume_x_dim = int(round(self.global_settings[Tags.DIM_VOLUME_X_MM] / voxel_spacing))
        volume_y_dim = int(round(self.global_settings[Tags.DIM_VOLUME_Y_MM] / voxel_spacing))
        volume_z_dim = int(round(self.global_settings[Tags.DIM_VOLUME_Z_MM] / voxel_spacing))

        if Tags.ACOUSTIC_SIMULATION_3D not in self.component_settings or not \
                self.component_settings[Tags.ACOUSTIC_SIMULATION_3D]:
            sizes = (volume_z_dim, volume_x_dim)
            sensor_map = np.zeros(sizes)
            sensor_map[detector_positions_voxels[:, 2]+1, detector_positions_voxels[:, 0]+1] = 1
        else:
            sizes = (volume_z_dim, volume_y_dim, volume_x_dim)
            sensor_map = np.zeros(sizes)
            sensor_map[detector_positions_voxels[:, 2]+1,
                       detector_positions_voxels[:, 1]+1,
                       detector_positions_voxels[:, 0]+1] = 1

        possible_acoustic_properties = [Tags.PROPERTY_SPEED_OF_SOUND,
                                        Tags.PROPERTY_DENSITY,
                                        Tags.PROPERTY_ALPHA_COEFF
                                        ]
        input_data[Tags.PROPERTY_SENSOR_MASK] = sensor_map

        volumes = tmp_ac_properties

        for acoustic_property in possible_acoustic_properties:
            if acoustic_property in tmp_ac_properties.keys():
                try:
                    input_data[acoustic_property] = np.rot90(volumes[acoustic_property], 3, axes=axes)
                except ValueError or KeyError:
                    self.logger.error("{} not specified.".format(acoustic_property))

        return input_data

    def reorder_time_series_data(self, time_series_sensor_data, detection_geometry):
        """
        Reorders the time series data to match the order that is assumed by kwave
        during image reconstruction with TimeReversal.

        The main issue here is, that, while forward modelling allows for the definition of
        3D cuboid bounding boxes for the detector elements, TimeReversal does not implement
        this feature.
        Instead, a binary mask is given and these are indexed in a column-row-wise manner in
        the output.
        The default np.argsort() method does not yield the same result as expected by
        k-Wave. Hence, this workaround.
        """
        def sort_order(positions):
            _sort_order = np.zeros((len(positions)))
            for i in range(len(_sort_order)):
                _sort_order[i] = (positions[i, 0] * 100000000000 +
                                  positions[i, 1] * 100000 +
                                  positions[i, 2])
            return _sort_order
        pa_device = detection_geometry
        detector_positions = pa_device.get_detector_element_positions_accounting_for_device_position_mm(
            self.global_settings)
        index_array = np.argsort(sort_order(detector_positions))
        return time_series_sensor_data[index_array]

    def reconstruction_algorithm(self, time_series_sensor_data, detection_geometry):
        input_data = dict()

        time_series_sensor_data = self.reorder_time_series_data(time_series_sensor_data, detection_geometry)

        input_data[Tags.TIME_SERIES_DATA] = time_series_sensor_data
        input_data = self.get_acoustic_properties(input_data, detection_geometry)
        acoustic_path = self.global_settings[Tags.SIMPA_OUTPUT_PATH] + ".mat"

        possible_k_wave_parameters = [Tags.SPACING_MM, Tags.UPSCALE_FACTOR,
                                      Tags.PROPERTY_ALPHA_POWER, Tags.GPU, Tags.PMLInside, Tags.PMLAlpha, Tags.PlotPML,
                                      Tags.RECORDMOVIE, Tags.MOVIENAME, Tags.ACOUSTIC_LOG_SCALE,
                                      Tags.SENSOR_DIRECTIVITY_PATTERN]

        pa_device = detection_geometry
        k_wave_settings = Settings({
            Tags.SENSOR_NUM_ELEMENTS: pa_device.number_detector_elements,
            Tags.SENSOR_DIRECTIVITY_SIZE_M: pa_device.detector_element_width_mm / 1000,
            Tags.SENSOR_CENTER_FREQUENCY_HZ: pa_device.center_frequency_Hz,
            Tags.SENSOR_BANDWIDTH_PERCENT: pa_device.bandwidth_percent
        })

        for parameter in possible_k_wave_parameters:
            if parameter in self.component_settings:
                k_wave_settings[parameter] = self.component_settings[parameter]
            elif parameter in self.global_settings:
                k_wave_settings[parameter] = self.global_settings[parameter]

        if Tags.K_WAVE_SPECIFIC_DT in self.global_settings and Tags.K_WAVE_SPECIFIC_NT in self.global_settings:
            k_wave_settings["dt"] = self.global_settings[Tags.K_WAVE_SPECIFIC_DT]
            k_wave_settings["Nt"] = self.global_settings[Tags.K_WAVE_SPECIFIC_NT]
        else:
            num_samples = time_series_sensor_data.shape[1]
            time_per_sample_s = 1 / (self.global_settings[Tags.SENSOR_SAMPLING_RATE_MHZ] * 1000000)
            k_wave_settings["dt"] = time_per_sample_s
            k_wave_settings["Nt"] = num_samples
        input_data["settings"] = k_wave_settings
        sio.savemat(acoustic_path, input_data, long_field_names=True)

        if Tags.ACOUSTIC_SIMULATION_3D in self.component_settings and \
                self.component_settings[Tags.ACOUSTIC_SIMULATION_3D]:
            time_reversal_script = "time_reversal_3D"
        else:
            time_reversal_script = "time_reversal_2D"

        base_script_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

        cmd = list()
        cmd.append(self.component_settings[Tags.ACOUSTIC_MODEL_BINARY_PATH])
        cmd.append("-nodisplay")
        cmd.append("-nosplash")
        cmd.append("-automation")
        cmd.append("-wait")
        cmd.append("-r")
        cmd.append("addpath('" + base_script_path + "');" +
                   time_reversal_script + "('" + acoustic_path + "');exit;")

        cur_dir = os.getcwd()
        os.chdir(self.global_settings[Tags.SIMULATION_PATH])
        self.logger.info(cmd)
        subprocess.run(cmd)

        reconstructed_data = sio.loadmat(acoustic_path + "tr.mat")[Tags.RECONSTRUCTED_DATA]

        os.chdir(cur_dir)
        os.remove(acoustic_path)
        os.remove(acoustic_path + "tr.mat")

        return reconstructed_data