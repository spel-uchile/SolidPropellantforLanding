"""
Created: 7/15/2020
Autor: Elias Obreque Sepulveda
email: els.obrq@gmail.com

"""

import numpy as np
import pandas as pd
from Thrust.PropellantGrain import PropellantGrain

DEG2RAD = np.pi/180

NEUTRAL  = 'neutral'
TUBULAR = 'tubular'
BATES   = 'bates'
STAR    = 'star'
PROGRESSIVE = 'progressive'
REGRESSIVE = 'regressive'


class Thruster(object):
    def __init__(self, dt, thruster_properties, propellant_properties, burn_type=None):
        self.thrust_profile = None
        self.burn_type = burn_type
        self.propellant_geometry = propellant_properties['propellant_geometry']
        if thruster_properties['engine_diameter_ext'] is not None:
            throat_diameter = thruster_properties['throat_diameter']
            engine_diameter_ext = thruster_properties['engine_diameter_ext']
            height = thruster_properties['height']
            volume_convergent_zone = (np.pi * height * (engine_diameter_ext * 0.5) ** 2) / 3
            self.volume_case = volume_convergent_zone
        self.step_width = dt
        self.selected_propellant = PropellantGrain(dt, propellant_properties)
        if self.selected_propellant.geometry_grain is not None:
            self.volume_case += self.selected_propellant.selected_geometry.free_volume
        else:
            self.t_burn = thruster_properties['performance']['t_burn']
            self.current_alpha = thruster_properties['performance']['alpha']
        if thruster_properties['load_thrust_profile']:
            self.thrust_profile, self.time_profile = self.load_thrust_profile(thruster_properties['file_name'])
            self.dt_profile = self.time_profile[1] - self.time_profile[0]
        self.current_burn_time = 0
        self.historical_mag_thrust = []
        self.t_ig = 0
        self.thr_is_on = False
        self.thr_is_burned = False
        self.current_time = 0
        self.current_mag_thrust_c = 0
        self.lag_coef = 0.00
        self.dead_time = 0.0
        self.current_beta = 0

        # variable for model the tanh function
        self.dx = 1
        if thruster_properties['lag_coef'] is not None:
            self.lag_coef = thruster_properties['lag_coef']
        if thruster_properties['dead_time'] is not None:
            self.dead_time = thruster_properties['dead_time']
            self.dx = (self.lag_coef + self.dead_time)/self.dead_time - 1
        self.delay_time_percentage = 0.1
        self.max_value_at_lag_coef = 0.999
        self.percentage_pro_ini = 0.3
        self.percentage_pro_end = self.max_value_at_lag_coef
        self.percentage_reg_ini = self.max_value_at_lag_coef
        self.percentage_reg_end = 0.3
        dy = (np.arctanh(self.max_value_at_lag_coef * 2 - 1) - np.arctanh(self.delay_time_percentage * 2 - 1))
        self.incline = dy/self.dx
        self.g_displacer_point = 1 - np.arctanh(self.delay_time_percentage * 2 - 1) / self.incline
        self.time_to_rise = (self.g_displacer_point + np.arctanh(self.max_value_at_lag_coef * 2 - 1) / self.incline) *\
                            self.dead_time
        self.calc_thah_model_parameters()

    def calc_thah_model_parameters(self):
        self.time_pro_intersection = (np.arctanh(2 * self.percentage_pro_ini - 1)
                                      / self.incline + self.g_displacer_point) * self.dead_time
        self.time_reg_intersection = self.t_burn + 2 * self.dead_time - \
                                     (np.arctanh(2 * self.percentage_reg_end - 1)
                                      / self.incline + self.g_displacer_point) * self.dead_time
        self.slope_reg = (self.percentage_reg_end - self.percentage_reg_ini) / (
                self.time_reg_intersection - self.dead_time - self.lag_coef)
        self.slope_pro = (self.percentage_pro_end - self.percentage_pro_ini) / (
                    self.dead_time + self.t_burn - self.lag_coef - self.time_pro_intersection)
        self.c_pro = self.percentage_pro_ini - self.slope_pro * self.time_pro_intersection
        self.c_reg = self.max_value_at_lag_coef - self.slope_reg * (self.dead_time + self.lag_coef)

    def set_lag_coef(self, val):
        self.lag_coef = val

    def reset_variables(self):
        self.t_ig = 0
        self.thr_is_on = False
        self.current_beta = 0
        self.current_burn_time = 0
        self.current_time = 0
        self.current_mag_thrust_c = 0
        self.thr_is_burned = False
        self.selected_propellant.update_dead_time()

    def propagate_thr(self):
        if self.selected_propellant.geometry_grain is not None:
            """Propagate propellant by model"""
        elif self.thrust_profile is not None:
            """Propagate loaded profile by file"""
            self.calc_parametric_thrust()
        else:
            """Propagate thrust by model"""
            if self.burn_type == PROGRESSIVE:
                if self.lag_coef == 0.0:
                    self.get_progressive_thrust()
                else:
                    self.get_progressive_thrust_with_lag()
            elif self.burn_type == REGRESSIVE:
                if self.lag_coef == 0.0:
                    self.get_regressive_thrust()
                else:
                    self.get_regressive_thrust_with_lag()
            else:
                if self.lag_coef == 0.0:
                    self.get_neutral_thrust()
                else:
                    self.get_neutral_thrust_with_lag()
        return

    def get_progressive_thrust(self):
        return

    def get_regressive_thrust(self):
        return

    def get_neutral_thrust(self):
        if self.thr_is_on:
            if self.current_burn_time == 0:
                self.selected_propellant.update_bias_isp()
                self.current_mag_thrust_c = self.current_alpha * self.selected_propellant.get_c_char()
                self.current_burn_time += self.step_width
            elif self.current_burn_time <= self.t_burn:
                self.selected_propellant.update_noise_isp()
                self.current_mag_thrust_c = self.current_alpha * self.selected_propellant.get_c_char()
                self.current_burn_time += self.step_width
            else:
                self.current_mag_thrust_c = 0
                self.thr_is_burned = True
                self.current_time += self.step_width
        else:
            self.current_mag_thrust_c = 0
            self.current_time += self.step_width
        return

    def get_current_thrust(self):
        return self.current_mag_thrust_c

    def set_alpha(self, value):
        self.current_alpha = value

    def set_t_burn(self, value):
        self.t_burn = value
        self.calc_thah_model_parameters()

    def calc_parametric_thrust(self):
        if self.thr_is_on:
            if self.current_burn_time == 0:
                self.current_mag_thrust_c = self.thrust_profile[0]
                self.current_burn_time += self.step_width
            elif self.current_burn_time <= max(self.time_profile):
                self.current_mag_thrust_c = self.thrust_profile[int(self.current_burn_time / self.dt_profile)]
                self.current_burn_time += self.step_width
            else:
                self.current_mag_thrust_c = 0
                self.thr_is_burned = True
                self.current_time += self.step_width
        else:
            self.current_mag_thrust_c = 0
            self.current_time += self.step_width

    def calc_tanh_model(self, to):
        if to == 'rising':
            return (1 + np.tanh((self.current_burn_time / self.dead_time - self.g_displacer_point) * self.incline)) * 0.5
        elif to == 'decaying':
            return (1 + np.tanh((-self.g_displacer_point - (self.current_burn_time - self.t_burn - 2 * self.dead_time)
                                 / self.dead_time) * self.incline)) * 0.5

    def get_neutral_thrust_with_lag(self):
        if self.thr_is_on:
            if self.current_burn_time == 0:
                self.selected_propellant.update_bias_isp()
                self.current_mag_thrust_c = 0
                self.current_burn_time += self.step_width
            elif self.current_burn_time <= self.dead_time + self.t_burn/2:
                current_max_thrust = self.current_alpha * self.selected_propellant.get_update_noise_isp()
                self.current_mag_thrust_c = current_max_thrust * self.calc_tanh_model('rising')
                self.current_time += self.step_width
                self.current_burn_time += self.step_width
            elif self.lag_coef + self.dead_time + self.t_burn >= self.current_burn_time: #> self.dead_time + self.t_burn/2:
                current_max_thrust = self.current_alpha * self.selected_propellant.get_update_noise_isp()
                self.current_mag_thrust_c = current_max_thrust * self.calc_tanh_model('decaying')
                self.current_time += self.step_width
                self.current_burn_time += self.step_width
            else:
                self.current_mag_thrust_c = 0
                self.thr_is_burned = True
                self.current_time += self.step_width
        else:
            self.current_mag_thrust_c = 0
            self.current_time += self.step_width

    def get_regressive_thrust_with_lag(self):
        if self.thr_is_on:
            if self.current_burn_time == 0:
                self.selected_propellant.update_bias_isp()
                self.current_mag_thrust_c = 0
                self.current_burn_time += self.step_width
            elif self.current_burn_time <= self.dead_time + self.lag_coef:
                current_max_thrust = self.current_alpha * self.selected_propellant.get_update_noise_isp()
                self.current_mag_thrust_c = current_max_thrust * self.calc_tanh_model('rising')
                self.current_burn_time += self.step_width
                self.current_time += self.step_width
            elif self.current_burn_time <= self.time_reg_intersection:
                current_max_thrust = self.current_alpha * self.selected_propellant.get_update_noise_isp()
                self.current_mag_thrust_c = current_max_thrust * (self.slope_reg * self.current_burn_time + self.c_reg)
                self.current_time += self.step_width
                self.current_burn_time += self.step_width
            elif self.current_burn_time <= self.dead_time + self.t_burn + self.lag_coef:
                current_max_thrust = self.current_alpha * self.selected_propellant.get_update_noise_isp()
                self.current_mag_thrust_c = current_max_thrust * self.calc_tanh_model('decaying')
                self.current_time += self.step_width
                self.current_burn_time += self.step_width
            else:
                self.current_mag_thrust_c = 0
                self.thr_is_burned = True
                self.current_time += self.step_width
        else:
            self.current_mag_thrust_c = 0
            self.current_time += self.step_width

    def get_progressive_thrust_with_lag(self):
        if self.thr_is_on:
            if self.current_burn_time == 0:
                self.selected_propellant.update_bias_isp()
                self.current_mag_thrust_c = 0
                self.current_burn_time += self.step_width
            elif self.current_burn_time <= self.time_pro_intersection:
                current_max_thrust = self.current_alpha * self.selected_propellant.get_update_noise_isp()
                self.current_mag_thrust_c = current_max_thrust * self.calc_tanh_model('rising')
                self.current_burn_time += self.step_width
                self.current_time += self.step_width
            elif self.current_burn_time <= self.dead_time + self.t_burn - self.lag_coef:
                current_max_thrust = self.current_alpha * self.selected_propellant.get_update_noise_isp()
                self.current_mag_thrust_c = current_max_thrust * (self.slope_pro * self.current_burn_time + self.c_pro)
                self.current_time += self.step_width
                self.current_burn_time += self.step_width
            elif self.current_burn_time <= self.dead_time + self.t_burn + self.lag_coef:
                current_max_thrust = self.current_alpha * self.selected_propellant.get_update_noise_isp()
                self.current_mag_thrust_c = current_max_thrust * self.calc_tanh_model('decaying')
                self.current_time += self.step_width
                self.current_burn_time += self.step_width
            else:
                self.current_mag_thrust_c = 0
                self.thr_is_burned = True
                self.current_time += self.step_width
        else:
            self.current_mag_thrust_c = 0
            self.current_time += self.step_width

    def set_beta(self, beta, n_engine=0):
        if self.thr_is_burned:
            self.thr_is_on = False
        else:
            if beta == 1 and self.current_beta == 0:
                if self.selected_propellant.current_dead_time >= self.selected_propellant.dead_time:
                    self.current_beta = beta
                    self.t_ig = self.current_time
                    self.thr_is_on = True
                    # print('thrust ', n_engine, ' ON')
                else:
                    self.selected_propellant.step_dead_time()
            elif beta == 1 and self.current_beta == 1:
                self.current_beta = beta
            elif self.thr_is_on:
                self.current_beta = 1
            else:
                self.current_beta = 0
                self.thr_is_on = False

    def log_value(self):
        self.historical_mag_thrust.append(self.current_mag_thrust_c)

    @staticmethod
    def load_thrust_profile(file_name):
        dataframe = pd.read_csv("Thrust/" + file_name)
        return dataframe['Thrust(N)'].values, dataframe['Time(s)'].values


if __name__ == '__main__':
    from Thrust.PropellantGrain import propellant_data
    from tools.Viewer import plot_thrust

    TUBULAR = 'tubular'
    BATES = 'bates'
    STAR = 'star'

    NEUTRAL = 'neutral'
    PROGRESSIVE = 'progressive'
    REGRESSIVE = 'regressive'

    m0 = 24
    propellant_name = 'CDT(80)'
    selected_propellant = propellant_data[propellant_name]
    propellant_geometry = TUBULAR
    Isp = selected_propellant['Isp']
    den_p = selected_propellant['density']
    ge = 9.807
    c_char = Isp * ge
    g_center_body = -1.62
    r_moon = 1738e3
    mu = 4.9048695e12
    reference_frame = '1D'
    dt = 0.01

    engine_diameter_ext = None
    throat_diameter = 1.0  # mm
    height = 10.0  # mm
    file_name = "Thrust/StarGrain7.csv"

    propellant_properties_ = {'propellant_name': propellant_name,
                              'n_thrusters': 1,
                              'pulse_thruster': 1,
                              'geometry': None,
                              'propellant_geometry': propellant_geometry,
                              'isp_noise_std': None,
                              'isp_bias_std': None,
                              'isp_dead_time_max': 0.0}

    ctrl_a = [1.0]
    ctrl_b = [6.91036]
    optimal_alpha = 1 / Isp / ge
    t_burn = 5
    json_list = {'1': {'Best_individual': [optimal_alpha, t_burn, ctrl_a, ctrl_b]}}

    percentage_variation = 3
    upper_isp = Isp * (1.0 + percentage_variation / 100.0)
    propellant_properties_['isp_noise_std'] = (upper_isp - Isp) / 3

    percentage_variation = 10
    upper_isp = Isp * (1.0 + percentage_variation / 100.0)
    propellant_properties_['isp_bias_std'] = (upper_isp - Isp) / 3

    dead_time = 1
    lag_coef = 0.5
    thruster_properties_ = {'throat_diameter': 2,
                            'engine_diameter_ext': engine_diameter_ext,
                            'height': height,
                            'performance': {'alpha': optimal_alpha,
                                            't_burn': t_burn},
                            'load_thrust_profile': False,
                            'file_name': file_name,
                            'dead_time': dead_time,
                            'lag_coef': lag_coef}

    n_thruster = 1
    comp_thrust = []
    for i in range(n_thruster):
        comp_thrust.append(Thruster(dt, thruster_properties_, propellant_properties_, burn_type=REGRESSIVE))

    propellant_properties_['isp_noise_std'] = None
    propellant_properties_['isp_bias_std'] = None

    comp_thrust_free = Thruster(dt, thruster_properties_, propellant_properties_, burn_type=REGRESSIVE)

    time_array = []
    k = 1
    current_time = 0

    while current_time <= 2 * t_burn + dead_time:
        time_array.append(current_time)
        thr = 0
        for i in range(n_thruster):
            comp_thrust[i].set_beta(1)
            comp_thrust[i].propagate_thr()
            comp_thrust[i].log_value()

        comp_thrust_free.set_beta(1)
        comp_thrust_free.propagate_thr()
        comp_thrust_free.log_value()

        current_time += dt

    total_thrust = 0
    for hist in comp_thrust:
        total_thrust += np.array(hist.historical_mag_thrust)

    plot_thrust(time_array, total_thrust, comp_thrust_free.historical_mag_thrust, ['Thrust: biased and noisy', 'Thrust: idealized'])
