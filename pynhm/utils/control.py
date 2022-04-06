import pathlib as pl
from typing import Union

from pynhm.base.DictAccess import DictAccess

# from .dictionary_as_properties import DictionaryAsProperties
from .prms5_file_util import PrmsFile

fileish = Union[str, pl.PosixPath, dict]
listish = Union[str, list, tuple]


# class ControlVariables:
#     """PRMS control file class

#     Args:
#         control_dict: control variable dictionary
#     """

#     def __init__(self, control_dict: dict) -> "ControlVariables":
#         self.control = DictionaryAsProperties(control_dict)

#     def get_variables(self, keys: listish) -> "ControlVariables":
#         """Get a subset of keys in the control variable dictionary

#         Args:
#             keys: keys to retrieve from the full PRMS control variable object

#         Returns:
#             ControlVariables : subset of full control variable dictionary
#                 Passed keys that do not exist in the full control variable
#                 dictionary are skipped.

#         """
#         if isinstance(keys, str):
#             keys = [keys]

#         return ControlVariables(
#             {
#                 key: self.control.get(key)
#                 for key in keys
#                 if key in self.control.keys()
#             }
#         )


class ControlVariables(DictAccess):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        return None

    @classmethod
    def load(cls, control_file: fileish) -> "ControlVariables":
        """Load variables from a PRMS control file

        Args:
            control_file: control file path

        Returns:
            ControlVariables: full PRMS control variable dictionary

        """
        return cls(
            PrmsFile(control_file, file_type="control").get_data()["control"]
        )
