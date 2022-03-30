import numpy as np

from ..atmosphere.NHMBoundaryLayer import NHMBoundaryLayer
from ..base.storageUnit import StorageUnit
from ..utils.parameters import PrmsParameters

NEARZERO = 1.0e-6
DNEARZERO = np.finfo(float).eps  # EPSILON(0.0D0)

RAIN = 0
SNOW = 1

BARESOIL = 0
GRASSES = 1

ACTIVE = 1

LAND = 1
LAKE = 2


class PRMSCanopy(StorageUnit):
    def __init__(
        self,
        params: PrmsParameters,
        atm: NHMBoundaryLayer,
        pkwater_equiv_alltimes: np.ndarray,
    ):

        verbose = True
        super().__init__("cnp", id, params, atm, verbose)

        # store pkwater_equiv, which is a snowpack calculated variable
        self.pkwater_equiv_alltimes = pkwater_equiv_alltimes

        # define self variables
        # todo: may need way to initialize interception storage to something non-zero
        self.intcp_stor_old = np.array(self.nhru * [0.0])
        self.intcp_stor = np.array(self.nhru * [0.0])
        self.tranpiration_on = True  # prms variable Transp_on
        self.covden = None  # will be set to covden_sum or covden_win
        self.interception_form = np.array(self.nhru * [RAIN], dtype=int)

        # define information on the output data that will be accessible
        self.output_data_names = [
            "intcpstor",
            "net_rain",
            "net_snow",
            "intcp_evap",
            "rainfall_adj",
            "snowfall_adj",
            "potet",
        ]
        self.initialize_output_data()

        # define information on inflows, outflows, and change in storage
        # todo: fill these out and implement a residual calculator?
        self.budget_inflows = [""]
        self.budget_outflows = [""]
        self.budget_change_in_storage = [""]

        return

    @staticmethod
    def get_required_parameters() -> list:
        """
        Returt a list of the paramaters required for this process

        """
        return [
            "nhru",
            "hru_area",
            "cov_type",
            "covden_sum",
            "covden_win",
            "srain_intcp",
            "wrain_intcp",
            "snow_intcp",
            "epan_coef",
            "potet_sublim",
        ]

    def advance(self, itime_step):
        self.intcp_stor_old = self.intcp_stor

        # set variables that depend on transpiration on/off setting
        # todo: this is currently hardwired to be on
        if self.tranpiration_on:
            self.covden = self.covden_sum
            self.stor_max_rain = self.srain_intcp
        else:
            self.covden = self.covden_win
            self.stor_max_rain = self.wrain_intcp

        self.interception_form[:] = RAIN
        snowfall = self.atm.get_current_state("snowfall")
        idx = np.where(snowfall > 0)
        self.interception_form[idx] = SNOW

        # pull out pkwater_equiv for this time (might need previous time because this is lagged)
        if itime_step == 0:
            self.pkwater_equiv = np.zeros(self.nhru)
        else:
            self.pkwater_equiv = self.pkwater_equiv_alltimes[itime_step - 1]

        assert self.pkwater_equiv.shape == (self.nhru,)

        return

    def calculate(self, time_length, vectorized=False):
        if vectorized:
            self.calculate_vectorized(time_length)
        else:
            self.calculate_procedural(time_length)
        return

    def calculate_procedural(self, time_length):

        # todo: verify that hru_ppt is prcp
        hru_ppt = self.atm.get_current_state("prcp")
        potet = self.atm.get_current_state("potet")
        hru_rain = self.atm.get_current_state("rainfall")
        hru_snow = self.atm.get_current_state("snowfall")

        net_rain = np.array(self.nhru * [0.0])
        net_snow = np.array(self.nhru * [0.0])
        net_ppt = np.array(self.nhru * [0.0])
        intcp_form = np.array(self.nhru * [RAIN])

        hru_type = np.array(self.nhru * [LAND])
        transp_on = np.array(self.nhru * [ACTIVE])
        intcp_evap = np.array(self.nhru * [0.0])
        hru_intcpstor = np.array(self.nhru * [0.0])

        for i in range(self.nhru):
            harea = self.hru_area[i]
            netrain = hru_rain[i]
            netsnow = hru_snow[i]

            cov = self.covden[i]
            intcp_form[i] = RAIN
            if hru_snow[i] > 0.0:
                intcp_form[i] = SNOW

            intcpstor = self.intcp_stor[i]
            intcpevap = 0.0
            changeover = 0.0
            extra_water = 0.0

            # lake or bare ground hrus
            if hru_type[i] == LAKE or self.cov_type[i] == BARESOIL:
                if self.cov_type[i] == BARESOIL and intcpstor > 0.0:
                    extra_water = self.intcp_stor[i]
                intcpstor = 0.0

            # todo: go from summer to winter cover density

            # todo: go from winter to summer cover density, excess = throughfall

            if transp_on[i] == ACTIVE:
                stor_max_rain = self.srain_intcp[i]
            else:
                stor_max_rain = self.wrain_intcp[i]

            # *****Determine the amount of interception from rain
            # IF ( Hru_type(i)/=LAKE .AND. Cov_type(i)/=BARESOIL ) THEN
            if hru_type[i] != LAKE and self.cov_type[i] != BARESOIL:
                if hru_rain[i] > 0.0:
                    if cov > 0.0:
                        # IF ( Cov_type(i)>GRASSES ) THEN
                        if self.cov_type[i] > GRASSES:
                            # intercept(Hru_rain(i), stor_max_rain, cov, intcpstor, netrain)
                            intcpstor, netrain = self.intercept(
                                hru_rain[i],
                                stor_max_rain,
                                cov,
                                intcpstor,
                                netrain,
                            )
                        elif self.cov_type[i] == GRASSES:
                            # IF ( Pkwater_equiv(i)<DNEARZERO .AND. netsnow<NEARZERO ) THEN
                            if (
                                self.pkwater_equiv[i] < DNEARZERO
                                and netsnow < NEARZERO
                            ):
                                intcpstor, netrain = self.intercept(
                                    hru_rain[i],
                                    stor_max_rain,
                                    cov,
                                    intcpstor,
                                    netrain,
                                )

            # ******Determine amount of interception from snow
            if hru_snow[i] > 0.0:
                if cov > 0.0:
                    if self.cov_type[i] > GRASSES:
                        intcpstor, netsnow = self.intercept(
                            hru_snow[i], stor_max_rain, cov, intcpstor, netsnow
                        )
                        if netsnow < NEARZERO:
                            netrain = netrain + netsnow
                            netsnow = 0.0
                            # todo: deal with newsnow and pptmix?
                            # Newsnow(i) = OFF
                            # Pptmix(i) = OFF

            # todo: canopy application of irrigation water based on irr_type

            # ******compute evaporation or sublimation of interception

            # if precipitation assume no evaporation or sublimation
            if intcpstor > 0.0:
                if hru_ppt[i] < NEARZERO:
                    epan_coef = 1.0
                    evrn = potet[i] / epan_coef
                    evsn = potet[i] * self.potet_sublim[i]

                    # todo: pan et
                    # IF ( Use_pandata==ACTIVE ) THEN
                    # evrn = Pan_evap(Hru_pansta(i))
                    # IF ( evrn<0.0 ) evrn = 0.0
                    # ENDIF

                    if intcp_form[i] == SNOW:
                        z = intcpstor - evsn
                        if z > 0:
                            intcpstor = z
                            intcpevap = evsn
                        else:
                            intcpevap = intcpstor
                            intcpstor = 0.0
                    else:
                        d = intcpstor - evrn
                        if d > 0.0:
                            intcpstor = d
                            intcpevap = evrn
                        else:
                            intcpevap = intcpstor
                            intcpstor = 0.0

            if intcpevap * cov > potet[i]:
                last = intcpevap
                if cov > 0.0:
                    intcpevap = potet[i] / cov
                else:
                    intcpevap = 0.0
                intcpstor = intcpstor + last - intcpevap

            intcp_evap[i] = intcpevap
            self.intcp_stor[i] = intcpstor
            hru_intcpstor[i] = intcpstor * cov
            net_rain[i] = netrain
            net_snow[i] = netsnow
            net_ppt[i] = netrain + netsnow

        self.output_data["intcpstor"].append(
            [self.atm.current_time] + list(hru_intcpstor)
        )
        self.output_data["net_rain"].append(
            [self.atm.current_time] + list(net_rain)
        )
        self.output_data["net_snow"].append(
            [self.atm.current_time] + list(net_snow)
        )
        self.output_data["intcp_evap"].append(
            [self.atm.current_time] + list(intcp_evap)
        )
        self.output_data["rainfall_adj"].append(
            [self.atm.current_time] + list(hru_rain)
        )
        self.output_data["snowfall_adj"].append(
            [self.atm.current_time] + list(hru_snow)
        )
        self.output_data["potet"].append([self.atm.current_time] + list(potet))

        return

    def calculate_vectorized(self, time_length):

        # Retrieve atmospheric forcings
        rainfall_adj = self.atm.get_current_state("rainfall")
        snowfall_adj = self.atm.get_current_state("snowfall")
        potet = self.atm.get_current_state("potet")
        prcp = self.atm.get_current_state("prcp")

        # initialize calculation variables
        net_rain = rainfall_adj.copy()
        net_snow = snowfall_adj.copy()
        intcp_stor = self.intcp_stor_old.copy()
        intcp_evap = np.array(self.nhru * [0.0])
        net_ppt = np.array(self.nhru * [0.0])

        # todo: Lakes not handled; but lakes are not in NHM so probably okay

        # todo: Handle changeover water going from summer to winter

        # todo: Handle changeover water going from winter to summer

        # update interception and net_rain
        idx = np.where(
            (self.cov_type != BARESOIL)
            & (self.covden > 0)
            & (self.cov_type > GRASSES)
        )
        self.update_net_precip(
            rainfall_adj,
            self.stor_max_rain,
            self.covden,
            intcp_stor,
            net_rain,
            idx,
        )
        idx = np.where(
            (self.cov_type == GRASSES)
            & (self.covden > 0.0)
            & (self.pkwater_equiv < NEARZERO)
            & (snowfall_adj < NEARZERO)
        )
        self.update_net_precip(
            rainfall_adj,
            self.stor_max_rain,
            self.covden,
            intcp_stor,
            net_rain,
            idx,
        )

        # Update intcp_stor and net_snow with snowfall for anything greater than grass
        idx = np.where((self.cov_type > GRASSES) & (self.covden > 0.0))
        self.update_net_precip(
            snowfall_adj,
            self.stor_max_rain,
            self.covden,
            intcp_stor,
            net_snow,
            idx,
        )

        # todo: Handle irrigation water?  Depends on whether or not this is part of NHM

        # todo: epan_coef is supposed to be specified by month; here it is fixed to 1.0
        epan_coef = 1.0

        # # if there is precip, then shut off potet and sublimation
        # evrn = np.where(prcp < NEARZERO, potet / epan_coef, 0.)
        # evsn = np.where(prcp < NEARZERO, potet * self.potet_sublim, 0.)
        # intcp_stor_save = intcp_stor.copy()
        # depth = np.where(
        #     self.interception_form == SNOW,
        #     intcp_stor - evsn,
        #     intcp_stor - evrn,
        # )
        # intcp_stor = np.maximum(depth, 0.0)
        # intcp_evap = intcp_stor_save - intcp_stor

        for i in range(self.nhru):
            intcpstor = intcp_stor[i]
            intcpevap = 0.0
            if intcpstor > 0.0:
                if prcp[i] < NEARZERO:
                    evrn = potet[i] / epan_coef
                    evsn = potet[i] * self.potet_sublim[i]

                    if self.interception_form[i] == SNOW:
                        z = intcpstor - evsn
                        if z > 0:
                            intcpstor = z
                            intcpevap = evsn
                        else:
                            intcpevap = intcpstor
                            intcpstor = 0.0
                    else:
                        d = intcpstor - evrn
                        if d > 0.0:
                            intcpstor = d
                            intcpevap = evrn
                        else:
                            intcpevap = intcpstor
                            intcpstor = 0.0
            intcp_stor[i] = intcpstor
            intcp_evap[i] = intcpevap

        # todo: adjust intcp_evap for cover density
        # todo: but this doesn't seem to make any sense
        # IF ( intcpevap*cov>Potet(i) ) THEN
        #  last = intcpevap
        #  IF ( cov>0.0 ) THEN
        #    intcpevap = Potet(i)/cov
        #  ELSE
        #    intcpevap = 0.0
        #  ENDIF
        #  intcpstor = intcpstor + last - intcpevap
        # ENDIF

        # accumulate into net_ppt
        net_ppt[:] = net_rain + net_snow

        self.intcp_stor[:] = intcp_stor[:]
        hru_intcpstor = intcp_stor * self.covden

        self.output_data["intcpstor"].append(
            [self.atm.current_time] + list(hru_intcpstor)
        )
        self.output_data["net_rain"].append(
            [self.atm.current_time] + list(net_rain)
        )
        self.output_data["net_snow"].append(
            [self.atm.current_time] + list(net_snow)
        )
        self.output_data["intcp_evap"].append(
            [self.atm.current_time] + list(intcp_evap)
        )
        self.output_data["rainfall_adj"].append(
            [self.atm.current_time] + list(rainfall_adj)
        )
        self.output_data["snowfall_adj"].append(
            [self.atm.current_time] + list(snowfall_adj)
        )

        return

    @staticmethod
    def intercept(precip, stor_max, cov, intcp_stor, net_precip):
        net_precip = precip * (1.0 - cov)
        intcp_stor = intcp_stor + precip
        if intcp_stor > stor_max:
            net_precip = net_precip + (intcp_stor - stor_max) * cov
            intcp_stor = stor_max
        return intcp_stor, net_precip

    @staticmethod
    def update_net_precip(
        precip, stor_max, covden, intcp_stor, net_precip, idx
    ):
        net_precip[idx] = precip[idx] * (1.0 - covden[idx])
        intcp_stor[idx] += precip[idx]
        for i in idx[0]:
            if intcp_stor[i] > stor_max[i]:
                net_precip[i] += (intcp_stor[i] - stor_max[i]) * covden[i]
                intcp_stor[i] = stor_max[i]
        return
