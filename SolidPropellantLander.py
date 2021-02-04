"""
Created: 9/14/2020
Author: Elias Obreque Sepulveda
email: els.obrq@gmail.com

array_propellant_names = ['JPL_540A', 'ANP-2639AF', 'CDT(80)', 'TRX-H609', 'KNSU']

"""
import numpy as np
import time
from datetime import datetime
from tools.GeneticAlgorithm import GeneticAlgorithm
from tools.ext_requirements import velocity_req, mass_req
from Dynamics.Dynamics import Dynamics
from Thrust.PropellantGrain import propellant_data

LINEAR = 'linear'
TUBULAR = 'tubular'
BATES = 'bates'
STAR = 'star'
ONE_D = '1D'
POLAR = 'polar'
now = datetime.now()
now = now.strftime("%Y-%m-%d")
reference_frame = ONE_D
# -----------------------------------------------------------------------------------------------------#
# Data Mars lander (12U (24 kg), 27U (54 kg))
m0 = 24
propellant_name = 'CDT(80)'
selected_propellant = propellant_data[propellant_name]
propellant_geometry = TUBULAR
Isp = selected_propellant['Isp']
den_p = selected_propellant['density']
ge = 9.807
c_char = Isp * ge

# Available space for engine (square)
space_max = 200  # mm
thickness_case_factor = 1.4
aux_dimension = 100  # mm

# -----------------------------------------------------------------------------------------------------#
# Center body data
# Moon
g_center_body = -1.62
r_moon = 1738e3
mu = 4.9048695e12

# -----------------------------------------------------------------------------------------------------#
# Initial position for 1D
r0 = 2000e3 - r_moon
v0 = 0

# Target localization
rd = 0
vd = 0

# -----------------------------------------------------------------------------------------------------#
# Initial position for Polar coordinate
rrp = 2000e3
rra = 68000e3
ra = 0.5 * (rra + rrp)
# Orbital velocity
vp = np.sqrt(mu * (2 / rrp - 1 / ra))
va = np.sqrt(mu * (2 / rra - 1 / ra))
print('Perilune velocity [m/s]: ', vp)
print('Apolune velocity [m/s]: ', va)
moon_period = 2 * np.pi * np.sqrt(ra ** 3 / mu)

p_r0 = rrp
p_v0 = 0
p_theta0 = 0
p_omega0 = vp / rrp
p_m0 = m0

# Target localization
p_rf = r_moon
p_vf = 0
p_thetaf = 0
p_omegaf = 0
p_mf = m0

# -----------------------------------------------------------------------------------------------------#
# Initial requirements for 1D
print('--------------------------------------------------------------------------')
print('1D requirements')
dv_req = np.sqrt(2 * r0 * np.abs(g_center_body))
print('Accumulated velocity[m/s]: ', dv_req)
mp, m1 = mass_req(dv_req, c_char, den_p, m0)

# Initial requirements for polar
print('\nPolar requirements')
dv_req_p, dv_req_a = velocity_req(vp, va, r_moon, mu, rrp, rra)
p_mp, p_m1 = mass_req(dv_req_p, c_char, den_p, m0)
print('--------------------------------------------------------------------------')

# -----------------------------------------------------------------------------------------------------#
# Simulation time
dt = 0.1
simulation_time = moon_period
# -----------------------------------------------------------------------------------------------------#
# System Propulsion properties
t_burn_min = 4  # s
t_burn_max = 100  # s
n_thruster = 20
par_force = 2  # Engines working simultaneously

pulse_thruster = int(n_thruster / par_force)

total_alpha_min = - g_center_body * m0 / c_char

# for 1D
total_alpha_max = mp / t_burn_min
print('Mass flow rate (1D): (min, max) [kg/s]', total_alpha_min, total_alpha_max)

# for Polar
total_alpha_max_p = p_mp / t_burn_min
print('Mass flow rate (Polar): (min, max) [kg/s]', total_alpha_min, total_alpha_max_p)

max_fuel_mass = 1.05 * mp  # Factor: 1.05

print('Required engines: (min-min, min-max, max-min, max-max) [-]',
      max_fuel_mass / total_alpha_min / t_burn_min,
      max_fuel_mass / total_alpha_min / t_burn_max,
      max_fuel_mass / total_alpha_max / t_burn_min,
      max_fuel_mass / total_alpha_max / t_burn_max)

print('Required engines: (min-min, min-max, max-min, max-max) [-]',
      max_fuel_mass / total_alpha_min / t_burn_min,
      max_fuel_mass / total_alpha_min / t_burn_max,
      max_fuel_mass / total_alpha_max_p / t_burn_min,
      max_fuel_mass / total_alpha_max_p / t_burn_max)

T_min = total_alpha_min * c_char
T_max = total_alpha_max * c_char
print('Max thrust: (min, max) [N]', T_min, T_max)
print('--------------------------------------------------------------------------')

# -----------------------------------------------------------------------------------------------------#
# Create dynamics object for 1D and Polar
dynamics = Dynamics(dt, Isp, g_center_body, mu, r_moon, m0, reference_frame, controller='basic_hamilton')

# -----------------------------------------------------------------------------------------------------#
# Simple example solution with constant one engine for 1D
dynamics.calc_limits_by_single_hamiltonian(t_burn_min, t_burn_max, total_alpha_min, total_alpha_max, plot_data=False)

# Calculate optimal alpha (m_dot) for a given t_burn
t_burn = 0.5 * (t_burn_min + t_burn_max)
total_alpha_max = 0.9 * m0 / t_burn
optimal_alpha = dynamics.basic_hamilton_calc.calc_simple_optimal_parameters(r0, total_alpha_min, total_alpha_max,
                                                                            t_burn)
# Define propellant properties to create a Thruster object with the optimal alpha
propellant_properties = {'propellant_name': propellant_name,
                         'n_thrusters': 1,
                         'pulse_thruster': 1,
                         'geometry': None,
                         'propellant_geometry': propellant_geometry,
                         'isp_std': None,
                         'isp_bias': None}

engine_diameter_ext = None
throat_diameter = 1.0  # mm
height = 10.0  # mm
file_name = "Thrust/StarGrain7.csv"
thruster_properties = {'throat_diameter': 2,
                       'engine_diameter_ext': engine_diameter_ext,
                       'height': height,
                       'performance': {'alpha': optimal_alpha,
                                       't_burn': t_burn},
                       'load_thrust_profile': False,
                       'file_name': file_name}

dynamics.set_engines_properties(thruster_properties, propellant_properties)

# Initial and final condition
x0 = [10000.0, v0, m0]
xf = [0.0, 0.0, m1]
time_options = [0, simulation_time, dt]

x_states, time_series, thr, _, _ = dynamics.run_simulation(x0, xf, time_options)
dynamics.basic_hamilton_calc.print_simulation_data(x_states, mp, m0, r0)
# dynamics.basic_hamilton_calc.plot_1d_simulation(x_states, time_series, thr)

# -----------------------------------------------------------------------------------------------------#
# Optimal solution with GA for constant thrust and multi-engines array
t_burn_min, t_burn_max = 2, 60
dynamics.controller_type = 'ga_wo_hamilton'

# initial condition
x0 = [5000.0, v0, m0]
time_options = [0.0, simulation_time, 0.05]
N_case = 20  # Case number

n_thruster = [8, 12, 16, 20, 24, 28]

for n_thr in n_thruster:
    pulse_thruster = int(n_thr / par_force)

    propellant_properties['n_thrusters'] = n_thr
    propellant_properties['pulse_thruster'] = pulse_thruster
    # +-10% and multi-engines array
    percentage_variation = 5
    lower_isp = Isp * (1.0 - percentage_variation / 100.0)
    upper_isp = Isp * (1.0 + percentage_variation / 100.0)

    # gauss_factor = 1 for 68.3%, = 2 for 95.45%, = 3 for 99.74%
    propellant_properties['isp_std'] = (upper_isp - Isp) / 3
    propellant_properties['isp_bias'] = None

    # Calculate optimal alpha (m_dot) for a given t_burn
    t_burn = 0.5 * (t_burn_min + t_burn_max)
    total_alpha_max = 0.9 * m0 / t_burn
    optimal_alpha = dynamics.basic_hamilton_calc.calc_simple_optimal_parameters(x0[0], total_alpha_min,
                                                                                total_alpha_max,
                                                                                t_burn)
    ga = GeneticAlgorithm(max_generation=200, n_individuals=50,
                          ranges_variable=[['float_iter', total_alpha_min/pulse_thruster,
                                            optimal_alpha * 2 / pulse_thruster, pulse_thruster],
                                           ['float_iter', 0, t_burn_max, pulse_thruster], ['str', LINEAR],
                                           ['float_iter', x0[0], xf[0], pulse_thruster]],
                          mutation_probability=0.2)


    def sp_cost_function(ga_x_states, thr, Ah, Bh):
        error_pos = ga_x_states[-1][0] - xf[0]
        error_vel = ga_x_states[-1][1] - xf[1]
        if max(np.array(ga_x_states)[:, 1]) > 0:
            error_vel *= 100
        if max(np.array(ga_x_states)[:, 0]) < 0:
            error_pos *= 100
        return Ah * error_pos ** 2 + Bh * error_vel ** 2 + 10 * (ga_x_states[0][2] / ga_x_states[-1][2]) ** 2


    start_time = time.time()
    best_states, best_time_data, best_Tf, best_individuals, index_control, end_index_control = ga.optimize(
        cost_function=sp_cost_function, n_case=N_case, restriction_function=[dynamics, x0, xf, time_options,
                                                                             propellant_properties,
                                                                             thruster_properties])
    finish_time = time.time()
    print('Time to optimize: ', finish_time - start_time)

    best_pos    = [best_states[i][:, 0] for i in range(N_case)]
    best_vel    = [best_states[i][:, 1] for i in range(N_case)]
    best_mass   = [best_states[i][:, 2] for i in range(N_case)]
    best_thrust = best_Tf

    df_list = []
    df_cost_list = []
    for k in range(N_case):
        df = {'Time[s]': best_time_data[k], 'Pos[m]': best_pos[k],
              'V[m/s]': best_vel[k], 'mass[kg]': best_mass[k],
              'T[N]': best_thrust[k]}
        df_cost = {'Cost_function[-]': np.array(ga.historical_cost)[:, k]}
        df_list.append(df)
        df_cost_list.append(df_cost)

    folder_name = "Only_GA_isp_noise/" + "n_thr-" + str(n_thr) + "_h-" + str(int(x0[0])) + "m/"

    file_name_1 = "Out_data_" + now
    file_name_2 = "Cost_function_" + now
    file_name_3 = "Sigma_Distribution_" + now
    file_name_4 = "Normal_Distribution_" + now
    ga.save_data(df_list, folder_name, file_name_1)
    ga.save_data(df_cost_list, folder_name, file_name_2)

    print(best_individuals[1])
    lim_std3sigma = [1, 3]  # [m, m/S]
    ga.plot_sigma_distribution(best_pos, best_vel, folder_name, file_name_3, lim_std3sigma, save=True)
    ga.plot_gauss_distribution(best_pos, best_vel, folder_name, file_name_4, save=True)
    ga.plot_best(best_time_data, best_pos, best_vel, best_mass, best_thrust, index_control,
                 end_index_control, save=True, folder_name=folder_name, file_name=file_name_1)
    ga.plot_state_vector(best_pos, best_vel, index_control, end_index_control, save=True,
                         folder_name=folder_name, file_name=file_name_2)

# -----------------------------------------------------------------------------------------------------#
# Optimal solution with GA for constant thrust with a

# plot
# opt_plot1 = '-b'
# opt_plot2 = 'or'
# create_plot()

# for i in range(N_case):
#     set_plot(1, time[i], x1[i], opt_plot1, opt_plot2)
#     set_plot(2, time[i], x2[i], opt_plot1, opt_plot2)
#     set_plot(3, time[i], x3[i], opt_plot1, opt_plot2)
#     set_plot(4, time[i], x4[i], opt_plot1, opt_plot2)
#     set_plot(5, time[i], x5[i], opt_plot1, opt_plot2)
#     set_plot(6, time[i], thr[i], opt_plot1, opt_plot2)
#     set_plot(7, time[i], (np.array(x1[i]) - r_moon), opt_plot1, opt_plot2)
#     set_plot(8, np.array(x1[i]) * (np.sin(x3[i])), np.array(x1[i]) * (np.cos(x3[i])), opt_plot1, opt_plot2)
# plt.show()
# print('Finished')

#
# N_case = 1  # Case number
#
# # Generation of case (Monte Carlo)
# rN = MonteCarlo(r0, sdr, N_case).random_value()
# vN = MonteCarlo(v0, sdv, N_case).random_value()
# mN = MonteCarlo(m0, sdm, N_case).random_value()
#
# p_rN = MonteCarlo(p_r0, sdr, N_case).random_value()
# p_vN = MonteCarlo(p_v0, sdv, N_case).random_value()
# p_thetaN = MonteCarlo(p_theta0, sdv, N_case).random_value()
# p_omegaN = MonteCarlo(p_omega0, sdv, N_case).random_value()
# p_mN = MonteCarlo(p_m0, sdm, N_case).random_value()
print("Finished")
