# The MIT License (MIT)
#
# Copyright (c) 2021 Computer Assisted Medical Interventions Group, DKFZ
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated simpa_documentation files (the "Software"), to deal
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

import numpy as np

from simpa.core.device_digital_twins import DetectionGeometryBase
from simpa.utils import Settings, Tags


class CurvedArrayDetectionGeometry(DetectionGeometryBase):
    """
    This class represents a digital twin of a ultrasound detection device
    with a curved detection geometry.

    """

    def __init__(self, pitch_mm=0.5,
                 radius_mm=40,
                 focus_in_field_of_view_mm = None,
                 number_detector_elements=256,
                 detector_element_width_mm=0.24,
                 detector_element_length_mm=13,
                 center_frequency_hz=3.96e6,
                 bandwidth_percent=55,
                 sampling_frequency_mhz=40,
                 probe_height_mm=43.2):

        super().__init__(number_detector_elements=number_detector_elements,
                         detector_element_width_mm=detector_element_width_mm,
                         detector_element_length_mm=detector_element_length_mm,
                         center_frequency_hz=center_frequency_hz,
                         bandwidth_percent=bandwidth_percent,
                         sampling_frequency_mhz=sampling_frequency_mhz,
                         probe_height_mm=probe_height_mm,
                         probe_width_mm=2 * np.sin(pitch_mm / radius_mm * 128) * radius_mm)

        self.pitch_mm = pitch_mm
        self.radius_mm = radius_mm
        if focus_in_field_of_view_mm is None:
            focus_in_field_of_view_mm = np.array([0, 0, 8])

        self.focus_in_field_of_view_mm = focus_in_field_of_view_mm

    def check_settings_prerequisites(self, global_settings: Settings) -> bool:
        if global_settings[Tags.VOLUME_CREATOR] != Tags.VOLUME_CREATOR_VERSATILE:
            if global_settings[Tags.DIM_VOLUME_Z_MM] <= (self.probe_height_mm + 1):
                self.logger.error("Volume z dimension is too small to encompass the device in simulation!"
                                  "Must be at least {} mm but was {} mm"
                                  .format((self.probe_height_mm + 1),
                                          global_settings[Tags.DIM_VOLUME_Z_MM]))
                return False
            if global_settings[Tags.DIM_VOLUME_X_MM] <= self.probe_width_mm:
                self.logger.error("Volume x dimension is too small to encompass MSOT device in simulation!"
                                  "Must be at least {} mm but was {} mm"
                                  .format(self.probe_width_mm, global_settings[Tags.DIM_VOLUME_X_MM]))
                return False

        global_settings[Tags.SENSOR_CENTER_FREQUENCY_HZ] = self.center_frequency_Hz
        global_settings[Tags.SENSOR_SAMPLING_RATE_MHZ] = self.sampling_frequency_MHz
        global_settings[Tags.SENSOR_BANDWIDTH_PERCENT] = self.bandwidth_percent

        return True

    def get_detector_element_positions_base_mm(self) -> np.ndarray:

        pitch_angle = self.pitch_mm / self.radius_mm
        self.logger.debug(f"pitch angle: {pitch_angle}")
        detector_radius = self.radius_mm

        # if distortion is not None:
        #     focus[0] -= np.round(distortion[1] / (2 * global_settings[Tags.SPACING_MM]))

        detector_positions = np.zeros((self.number_detector_elements, 3))
        # go from -127.5, -126.5, ..., 0, .., 126.5, 177.5 instead of between -128 and 127
        det_elements = np.arange(-int(self.number_detector_elements / 2) + 0.5,
                                 int(self.number_detector_elements / 2) + 0.5)
        detector_positions[:, 0] = self.focus_in_field_of_view_mm[0] \
                                   + np.sin(pitch_angle * det_elements) * detector_radius
        detector_positions[:, 2] = self.focus_in_field_of_view_mm[2] \
                                   - np.sqrt(
            detector_radius ** 2 - (np.sin(pitch_angle * det_elements) * detector_radius) ** 2)

        return detector_positions

    def get_detector_element_orientations(self, global_settings: Settings) -> np.ndarray:
        detector_positions = self.get_detector_element_positions_base_mm()
        detector_orientations = np.subtract(self.focus_in_field_of_view_mm, detector_positions)
        norm = np.linalg.norm(detector_orientations, axis=-1)
        for dim in range(3):
            detector_orientations[:, dim] = detector_orientations[:, dim] / norm
        return detector_orientations

    def get_default_probe_position(self, global_settings: Settings) -> np.ndarray:
        sizes_mm = np.asarray([global_settings[Tags.DIM_VOLUME_X_MM],
                               global_settings[Tags.DIM_VOLUME_Y_MM],
                               global_settings[Tags.DIM_VOLUME_Z_MM]])
        return np.array([sizes_mm[0] / 2, sizes_mm[1] / 2, self.probe_height_mm])