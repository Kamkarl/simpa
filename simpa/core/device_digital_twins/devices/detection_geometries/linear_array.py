"""
SPDX-FileCopyrightText: 2021 Computer Assisted Medical Interventions Group, DKFZ
SPDX-FileCopyrightText: 2021 VISION Lab, Cancer Research UK Cambridge Institute (CRUK CI)
SPDX-License-Identifier: MIT
"""
import numpy as np

from simpa.core.device_digital_twins import DetectionGeometryBase
from simpa.utils import Settings, Tags


class LinearArrayDetectionGeometry(DetectionGeometryBase):
    """
    This class represents a digital twin of a ultrasound detection device
    with a linear detection geometry.

    """

    def get_field_of_view_extent_mm(self) -> np.ndarray:
        return np.asarray([-self.probe_width_mm/2,
                           self.probe_width_mm/2,
                           0, 0,
                           0, 100])

    def __init__(self, pitch_mm=0.5,
                 number_detector_elements=100,
                 detector_element_width_mm=0.24,
                 detector_element_length_mm=0.5,
                 center_frequency_hz=3.96e6,
                 bandwidth_percent=55,
                 sampling_frequency_mhz=40,
                 device_position_mm: np.ndarray = None):
        super().__init__(number_detector_elements=number_detector_elements,
                         detector_element_width_mm=detector_element_width_mm,
                         detector_element_length_mm=detector_element_length_mm,
                         center_frequency_hz=center_frequency_hz,
                         bandwidth_percent=bandwidth_percent,
                         sampling_frequency_mhz=sampling_frequency_mhz,
                         probe_width_mm=number_detector_elements * pitch_mm,
                         device_position_mm=device_position_mm)
        self.pitch_mm = pitch_mm

    def check_settings_prerequisites(self, global_settings: Settings) -> bool:
        if global_settings[Tags.DIM_VOLUME_X_MM] <= self.probe_width_mm:
            self.logger.error("Volume x dimension is too small to encompass MSOT device in simulation!"
                              "Must be at least {} mm but was {} mm"
                              .format(self.probe_width_mm, global_settings[Tags.DIM_VOLUME_X_MM]))
            return False
        return True

    def get_detector_element_positions_base_mm(self) -> np.ndarray:

        detector_positions = np.zeros((self.number_detector_elements, 3))

        det_elements = np.arange(-int(self.number_detector_elements / 2),
                                 int(self.number_detector_elements / 2)) * self.pitch_mm

        detector_positions[:, 0] = det_elements

        return detector_positions

    def get_detector_element_orientations(self, global_settings: Settings) -> np.ndarray:
        detector_orientations = np.zeros((self.number_detector_elements, 3))
        detector_orientations[:, 2] = -1
        return detector_orientations
