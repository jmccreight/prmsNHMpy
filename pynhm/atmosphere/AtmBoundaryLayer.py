from copy import deepcopy

import numpy as np

from pynhm.base.Time import Time

# This is a base AtmBoundaryLayer class
# It has no state, only time.

# JLM: where do we keep the metadata attributes?

# JLM: The state is concieved here as a timeseries, not just an instant or
# JLM: markov (previous and current).

# JLM: Are the forcings valid over the interval [current_time, current_time + time_step]?
# JLM: This should go in the attributes

# JLM: state or FLUX? differentiate? just in metadata? change nomenclature?


class AtmBoundaryLayer(Time):
    def __init__(
        self,
        start_time: np.datetime64 = None,
        time_step: np.timedelta64 = None,  # could we infer timestep?
        end_time: np.datetime64 = None,
        datetime: np.ndarray = None,
        height_m: int = None,
        verbosity: int = 0,
    ):
        super().__init__(
            start_time=start_time,
            time_step=time_step,
            end_time=end_time,
            verbosity=verbosity,
        )
        self.name = "AtmBoundaryLayer"
        self._coords += ["spatial_id"]
        self.height_m = height_m

        self.spatial_id = None

        return

    # JLM check that time and the time dimensions on the states match on set or inits
    # JLM ensure the spatial dimension matches.
