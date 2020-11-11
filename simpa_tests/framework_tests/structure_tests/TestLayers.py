# The MIT License (MIT)
#
# Copyright (c) 2018 Computer Assisted Medical Interventions Group, DKFZ
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

import unittest
import matplotlib.pyplot as plt
from simpa.utils.libraries.tissue_library import TISSUE_LIBRARY
from simpa.utils.deformation_manager import create_deformation_settings
from simpa.utils import Tags
from simpa.utils.settings_generator import Settings
from simpa.utils.libraries.structure_library import HorizontalLayerStructure


class TestLayers(unittest.TestCase):

    def setUp(self):
        self.global_settings = Settings()
        self.global_settings[Tags.SPACING_MM] = 1
        self.global_settings[Tags.SIMULATE_DEFORMED_LAYERS] = False
        self.global_settings[Tags.DEFORMED_LAYERS_SETTINGS] = create_deformation_settings(bounds_mm=[[0, 20], [0, 20]],
                                                                                          maximum_z_elevation_mm=3,
                                                                                          filter_sigma=0,
                                                                                          cosine_scaling_factor=4)
        self.global_settings[Tags.DIM_VOLUME_X_MM] = 2
        self.global_settings[Tags.DIM_VOLUME_Y_MM] = 2
        self.global_settings[Tags.DIM_VOLUME_Z_MM] = 6

        self.layer_settings = Settings()
        self.layer_settings[Tags.STRUCTURE_START_MM] = [0, 0, 0]
        self.layer_settings[Tags.STRUCTURE_END_MM] = [0, 0, 0]
        self.layer_settings[Tags.MOLECULE_COMPOSITION] = TISSUE_LIBRARY.muscle()
        self.layer_settings[Tags.ADHERE_TO_DEFORMATION] = True

    def assert_values(self, volume, values):
        assert abs(volume[0][0][0] - values[0]) < 1e-5, "excpected " + str(values[0]) + " but was " + str(volume[0][0][0])
        assert abs(volume[0][0][1] - values[1]) < 1e-5, "excpected " + str(values[1]) + " but was " + str(volume[0][0][1])
        assert abs(volume[0][0][2] - values[2]) < 1e-5, "excpected " + str(values[2]) + " but was " + str(volume[0][0][2])
        assert abs(volume[0][0][3] - values[3]) < 1e-5, "excpected " + str(values[3]) + " but was " + str(volume[0][0][3])
        assert abs(volume[0][0][4] - values[4]) < 1e-5, "excpected " + str(values[4]) + " but was " + str(volume[0][0][4])
        assert abs(volume[0][0][5] - values[5]) < 1e-5, "excpected " + str(values[5]) + " but was " + str(volume[0][0][5])

    def test_layer_structes_partial_volume_within_one_voxel(self):
        self.layer_settings[Tags.STRUCTURE_START_MM] = [0, 0, 1.3]
        self.layer_settings[Tags.STRUCTURE_END_MM] = [0, 0, 1.7]
        ls = HorizontalLayerStructure(self.global_settings, self.layer_settings)
        self.assert_values(ls.geometrical_volume, [0, 0.4, 0, 0, 0, 0])

    def test_layer_structes_partial_volume_within_two_voxels(self):
        self.layer_settings[Tags.STRUCTURE_START_MM] = [0, 0, 1.4]
        self.layer_settings[Tags.STRUCTURE_END_MM] = [0, 0, 2.5]
        ls = HorizontalLayerStructure(self.global_settings, self.layer_settings)
        self.assert_values(ls.geometrical_volume, [0, 0.6, 0.5, 0, 0, 0])

    def test_layer_structes_partial_volume_within_three_voxels(self):
        self.layer_settings[Tags.STRUCTURE_START_MM] = [0, 0, 1.3]
        self.layer_settings[Tags.STRUCTURE_END_MM] = [0, 0, 3.5]
        ls = HorizontalLayerStructure(self.global_settings, self.layer_settings)
        self.assert_values(ls.geometrical_volume, [0, 0.7, 1, 0.5, 0, 0])

    def test_layer_structes_partial_volume_close_to_border(self):
        self.layer_settings[Tags.STRUCTURE_START_MM] = [0, 0, 1.2]
        self.layer_settings[Tags.STRUCTURE_END_MM] = [0, 0, 2.1]
        ls = HorizontalLayerStructure(self.global_settings, self.layer_settings)
        self.assert_values(ls.geometrical_volume, [0, 0.8, 0.1, 0, 0, 0])

    def test_layer_structes_partial_volume_at_border(self):
        self.layer_settings[Tags.STRUCTURE_START_MM] = [0, 0, 1.2]
        self.layer_settings[Tags.STRUCTURE_END_MM] = [0, 0, 2.0]
        ls = HorizontalLayerStructure(self.global_settings, self.layer_settings)
        self.assert_values(ls.geometrical_volume, [0, 0.8, 0, 0, 0, 0])

        self.layer_settings[Tags.STRUCTURE_START_MM] = [0, 0, 1.0]
        self.layer_settings[Tags.STRUCTURE_END_MM] = [0, 0, 1.8]
        ls = HorizontalLayerStructure(self.global_settings, self.layer_settings)
        self.assert_values(ls.geometrical_volume, [0, 0.8, 0, 0, 0, 0])



