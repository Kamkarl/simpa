"""
SPDX-FileCopyrightText: 2021 Computer Assisted Medical Interventions Group, DKFZ
SPDX-FileCopyrightText: 2021 VISION Lab, Cancer Research UK Cambridge Institute (CRUK CI)
SPDX-License-Identifier: MIT
"""

from abc import ABC, abstractmethod


class SerializableSIMPAClass(ABC):
    """
    TODO
    """

    @abstractmethod
    def serialize(self) -> dict:
        pass

    @staticmethod
    @abstractmethod
    def deserialize(dictionary_to_deserialize: dict):
        pass