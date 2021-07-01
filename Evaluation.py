"""
Created by:

@author: Elias Obreque
@Date: 4/19/2021 8:21 PM 
els.obrq@gmail.com

"""
from tools.MonteCarlo import MonteCarlo
from tools.Viewer import *


class Evaluation(object):
    def __init__(self, dynamics, x0, xf, time_options, json_list, control_function, thruster_properties, propellant_properties, type_propellant):
        self.dynamics = dynamics
        self.x0 = x0
        self.xf = xf
        self.time_options = time_options
        self.json_list = json_list
        self.dynamics.controller_function = control_function
        self.dynamics.set_engines_properties(thruster_properties, propellant_properties, type_propellant)

    def propagate(self, n_case, n_thrusters, state_noise=None):
        # # Generation of case (Monte Carlo)
        rN = []
        vN = []
        mN = []

        state_noise_flag = False
        if state_noise is not None:
            state_noise_flag = state_noise[0]
            sdr = state_noise[1]
            sdv = state_noise[2]
            sdm = state_noise[3]
            rN = MonteCarlo(self.x0[0], sdr, n_case).random_value()
            vN = MonteCarlo(self.x0[1], sdv, n_case).random_value()
            mN = MonteCarlo(self.x0[2], sdm, n_case).random_value()

        X_states = []
        THR = []
        IC = []
        EC = []
        TIME = []
        LAND_INDEX = []

        for n_thr in n_thrusters:
            if type(self.json_list[str(n_thr)]['Best_individual'][0]) == float:
                for j in range(n_thr):
                    self.dynamics.modify_individual_engine(j, 'alpha',
                                                           self.json_list[str(n_thr)]['Best_individual'][0])
                    self.dynamics.modify_individual_engine(j, 't_burn',
                                                           self.json_list[str(n_thr)]['Best_individual'][1])
            else:
                for j in range(n_thr):
                    self.dynamics.modify_individual_engine(j, 'alpha',
                                                           self.json_list[str(n_thr)]['Best_individual'][0][j])
                    self.dynamics.modify_individual_engine(j, 't_burn',
                                                           self.json_list[str(n_thr)]['Best_individual'][1][j])

            self.dynamics.set_controller_parameters(self.json_list[str(n_thr)]['Best_individual'][2:])
            X_states.append([])
            THR.append([])
            IC.append([])
            EC.append([])
            TIME.append([])
            LAND_INDEX.append([])
            for k in range(n_case):
                if state_noise_flag:
                    x0_ = [rN[k], vN[k], mN[k]]
                else:
                    x0_ = self.x0

                x_, time_, thrust_, index_control_, end_index_control_, land_i_ = \
                    self.dynamics.run_simulation(x0_, self.xf, self.time_options)

                X_states[int(n_thr - 1)].append(x_)
                LAND_INDEX[int(n_thr - 1)].append(land_i_)
                THR[int(n_thr - 1)].append(thrust_)
                TIME[int(n_thr - 1)].append(time_)
                IC[int(n_thr - 1)].append(index_control_)
                EC[int(n_thr - 1)].append(end_index_control_)

                # Reset thruster
                for thrust in self.dynamics.thrusters:
                    thrust.reset_variables()

            pos_sim = [np.array(X_states[int(n_thr - 1)][i])[:, 0] for i in range(n_case)]
            vel_sim = [np.array(X_states[int(n_thr - 1)][i])[:, 1] for i in range(n_case)]
            mass_sim = [np.array(X_states[int(n_thr - 1)][i])[:, 2] for i in range(n_case)]
            thrust_sim = THR[int(n_thr - 1)]

            plot_main_parameters(TIME[int(n_thr - 1)], pos_sim, vel_sim, mass_sim, thrust_sim, IC[int(n_thr - 1)],
                                 EC[int(n_thr - 1)], save=False)
            plot_gauss_distribution(pos_sim, vel_sim, LAND_INDEX[int(n_thr - 1)], save=False)
            plot_state_vector(pos_sim, vel_sim, IC[int(n_thr - 1)], EC[int(n_thr - 1)], save=False)
            plt.show()


if __name__ == '__main__':
    from Dynamics.Dynamics import Dynamics
    from Thrust.PropellantGrain import propellant_data

    CONSTANT = 'constant'
    TUBULAR = 'tubular'
    BATES = 'bates'
    STAR = 'star'
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
    dt = 0.1

    # Initial position for 1D
    r0 = 2000
    v0 = 0

    # Target localization
    rd = 0
    vd = 0

    # Initial and final condition
    x0 = [r0, v0, m0]
    xf = [rd, vd, 0]
    time_options = [0, 100, dt]

    dynamics = Dynamics(dt, Isp, g_center_body, mu, r_moon, m0, reference_frame, controller='affine_function')

    propellant_properties = {'propellant_name': propellant_name,
                             'n_thrusters': 1,
                             'pulse_thruster': 1,
                             'geometry': None,
                             'propellant_geometry': propellant_geometry,
                             'isp_noise_std': None,
                             'isp_bias_std': None,
                             'isp_dead_time_max': 0.0}

    engine_diameter_ext = None
    throat_diameter = 1.0  # mm
    height = 10.0  # mm
    file_name = "Thrust/StarGrain7.csv"

    def control_function(control_par, current_state):
        a = control_par[0]
        b = control_par[1]
        current_alt = current_state[0]
        current_vel = current_state[1]
        f = a * current_alt + b * current_vel
        if f <= 0:
            return 1
        else:
            return 0

    ctrl_a = [1.0]
    ctrl_b = [6.91036]
    optimal_alpha = 0.0502
    t_burn = 13.53715
    json_list = {'1': {'Best_individual': [optimal_alpha, t_burn, ctrl_a, ctrl_b]}}

    thruster_properties = {'throat_diameter': 2,
                           'engine_diameter_ext': engine_diameter_ext,
                           'height': height,
                           'performance': {'alpha': optimal_alpha,
                                           't_burn': t_burn},
                           'load_thrust_profile': False,
                           'file_name': file_name,
                           'dead_time': None,
                           'lag_coef': None}

    n_case = 60
    type_propellant = CONSTANT
    n_thrusters = [1]

    evaluation = Evaluation(dynamics, x0, xf, time_options, json_list, control_function, thruster_properties,
                            propellant_properties,
                            type_propellant)
    evaluation.propagate(n_case, n_thrusters, state_noise=[True, 50.0, 5.0, 0.0])

    print('end')