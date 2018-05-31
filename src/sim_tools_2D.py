"""
ColECM: Collagen ExtraCellular Matrix Simulation
SIMULATION 2D ROUTINE 

Created by: Frank Longford
Created on: 09/03/2018

Last Modified: 19/04/2018
"""

import numpy as np
import sys, os, pickle
from mpi4py import MPI

import utilities as ut


def cos_sin_theta(vector, r_vector):
	"""
	cos_sin_theta(vector, r_vector)

	Returns cosine and sine of angles of intersecting vectors betwen even and odd indicies

	Parameters
	----------

	vector:  array_like, (float); shape=(n_vector, n_dim)
		Array of displacement vectors between connecting beads

	r_vector: array_like, (float); shape=(n_vector)
		Array of radial distances between connecting beads

	Returns
	-------

	cos_the:  array_like (float); shape=(n_vector/2)
		Cosine of the angle between each pair of displacement vectors

	sin_the: array_like (float); shape=(n_vector/2)
		Sine of the angle between each pair of displacement vectors

	r_prod: array_like (float); shape=(n_vector/2)
		Product of radial distance between each pair of displacement vectors
	"""

	n_vector = int(vector.shape[0])
	n_dim = vector.shape[1]

	temp_vector = np.reshape(vector, (int(n_vector/2), 2, n_dim))

	"Calculate |rij||rjk| product for each pair of vectors"
	r_prod = np.prod(np.reshape(r_vector, (int(n_vector/2), 2)), axis = 1)

	"Form dot product of each vector pair rij*rjk in vector array corresponding to an angle"
	dot_prod = np.sum(np.prod(temp_vector, axis=1), axis=1)

	"Form pseudo-cross product of each vector pair rij*rjk in vector array corresponding to an angle"
	cross_prod = np.linalg.det(temp_vector)

	"Calculate cos(theta) for each angle"
	cos_the = dot_prod / r_prod

	"Calculate sin(theta) for each angle"
	sin_the = cross_prod / r_prod

	return cos_the, sin_the, r_prod


def calc_energy_forces(pos, cell_dim, pos_indices, bond_indices, frc_indices, angle_indices, angle_bond_indices, 
				vdw_coeff, virial_indicies, param):
	"""
	calc_energy_forces(distances, r2, bond_matrix, vdw_matrix, verlet_list, bond_beads, dist_index, r_index, param)

	Return tot potential energy and forces on each bead in simulation

	Parameters
	----------

	dxy:  array_like (float); shape=(2, n_bead, n_bead)
		Displacement along x and y axis between each bead

	r2:  array_like (float); shape=(n_bead, n_bead)
		Square of Radial disance between each bead

	bond_matrix: array_like (int); shape=(n_bead, n_bead)
		Matrix determining whether a bond is present between two beads

	verlet_list: array_like (int); shape=(n_bead, n_bead)
		Matrix determining whether two beads are within rc radial distance

	vdw_param: array_like (float); shape=(2)
		Sigma and epsilon paameters for Van de Waals forces

	bond_param: array_like (float); shape=(2)
		Equilibrium length and energy paameters for bonded forces

	angle_param: array_like (float); shape=(2)
		Equilibrium angle and energy paameters for angular forces

	rc:  float
		Interaction cutoff radius for non-bonded forces

	bond_beads:  array_like, (int); shape=(n_angle, 3)
		Array containing indicies in pos array all 3-bead angular interactions

	dxy_index:  array_like, (int); shape=(n_bond, 2)
		Array containing indicies in dx and dy arrays of all bonded interactions

	r_index:  array_like, (int); shape=(n_bond, 2)
		Array containing indicies in r array of all bonded interactions
		
	Returns
	-------

	pot_energy:  float
		Total potential energy of simulation cell

	frc_beads:  array_like (float); shape=(n_beads, n_dim)
		Forces acting upon each bead due to positional array

	virial_tensor:  array_like (float); shape=(n_dim, n_dim)
		Virial term of pressure tensor components

	"""

	#frc_beads = np.zeros((n_dim, n_bead))
	f_beads_x = np.zeros((pos.shape[0]))
	f_beads_y = np.zeros((pos.shape[0]))
	pot_energy = 0
	cut_frc = ut.force_vdw(param['rc']**2, param['vdw_sigma'], param['vdw_epsilon'])
	cut_pot = ut.pot_vdw(param['rc']**2, param['vdw_sigma'], param['vdw_epsilon'])
	virial_tensor = np.zeros((2, 2))
	n_bond = bond_indices[0].shape[0]

	pair_dist = ut.get_distances_mpi(pos, pos_indices, cell_dim)
	pair_r2 = np.sum(pair_dist**2, axis=0)

	if n_bond > 0:

		"Bond Lengths"
		bond_r = np.sqrt(pair_r2[bond_indices])
		#verlet_list_r0 = ut.check_cutoff(r_half, param['bond_r0'])
		#verlet_list_r1 = ut.check_cutoff(r_half, param['bond_r1'])

		bond_pot = ut.pot_harmonic(bond_r, param['bond_r0'], param['bond_k0'])# * verlet_list_r0
		#bond_pot_1 = ut.pot_harmonic(r_half, param['bond_r1'], param['bond_k1']) * verlet_list_r1
		pot_energy += 0.5 * np.sum(bond_pot)# + np.sum(bond_pot_1)

		bond_frc = ut.force_harmonic(bond_r, param['bond_r0'], param['bond_k0'])# * verlet_list_r0
		#bond_frc_1 = ut.force_harmonic(r_half, param['bond_r1'], param['bond_k1']) * verlet_list_r1

		temp_frc = np.zeros((2, pos.shape[0], pos.shape[0]))
		temp_frc[0][frc_indices] += bond_frc * pair_dist[0][bond_indices] / bond_r
		temp_frc[1][frc_indices] += bond_frc * pair_dist[1][bond_indices] / bond_r

		f_beads_x += np.sum(temp_frc[0], axis=1)
		f_beads_y += np.sum(temp_frc[1], axis=1)

		#for i in range(2):
		#	for j in range(2): virial_tensor[i][j] += np.sum(bond_frc / r_half * distances[i][indices_half] * distances[j][indices_half])

		"Bond Angles"
		try:
			angle_dist = (pos[angle_bond_indices[0]] - pos[angle_bond_indices[1]]).T
			for i in range(param['n_dim']): angle_dist[i] -= cell_dim[i] * np.array(2 * angle_dist[i] / cell_dim[i], dtype=int)
			angle_r2 = np.sum(angle_dist**2, axis=0)

			"Make array of vectors rij, rjk for all connected bonds"
			vector = np.stack((angle_dist[0], angle_dist[1]), axis=1)
			n_vector = int(vector.shape[0])

			"Find |rij| values for each vector"
			r_vector = np.sqrt(angle_r2)
			cos_the, sin_the, r_prod = cos_sin_theta(vector, r_vector)
			pot_energy += param['angle_k0'] * np.sum(cos_the + 1)

			"Form arrays of |rij| vales, cos(theta) and |rij||rjk| terms same shape as vector array"
			r_array = np.reshape(np.repeat(r_vector, 2), vector.shape)
			sin_the_array = np.reshape(np.repeat(sin_the, 4), vector.shape)
			r_prod_array = np.reshape(np.repeat(r_prod, 4), vector.shape)

			"Form left and right hand side terms of (cos(theta) rij / |rij|^2 - rjk / |rij||rjk|)"
			r_left = vector / r_prod_array
			r_right = sin_the_array * vector / r_array**2

			ij_indices = np.arange(0, n_vector, 2)
			jk_indices = np.arange(1, n_vector, 2)

			"Perfrom right hand - left hand term for every rij rkj pair"
			r_left[ij_indices] -= r_right[jk_indices]
			r_left[jk_indices] -= r_right[ij_indices] 
		
			"Calculate forces upon beads i, j and k"
			frc_angle_ij = param['angle_k0'] * r_left
			frc_angle_k = -np.sum(np.reshape(frc_angle_ij, (int(n_vector/2), 2, 2)), axis=1)

			"Add angular forces to force array" 
			f_beads_x[angle_indices.T[0]] += frc_angle_ij[ij_indices].T[0]
			f_beads_x[angle_indices.T[1]] += frc_angle_k.T[0]
			f_beads_x[angle_indices.T[2]] += frc_angle_ij[jk_indices].T[0]

			f_beads_y[angle_indices.T[0]] += frc_angle_ij[ij_indices].T[1]
			f_beads_y[angle_indices.T[1]] += frc_angle_k.T[1]
			f_beads_y[angle_indices.T[2]] += frc_angle_ij[jk_indices].T[1]

		except IndexError: pass
	
	verlet_list = ut.check_cutoff(pair_r2, param['rc']**2)
	non_zero = np.nonzero(pair_r2 * verlet_list)

	nonbond_pot = vdw_coeff[non_zero] * ut.pot_vdw((pair_r2 * verlet_list)[non_zero], param['vdw_sigma'], param['vdw_epsilon']) - cut_pot
	pot_energy += np.nansum(nonbond_pot) / 2

	nonbond_frc = vdw_coeff[non_zero] * ut.force_vdw((pair_r2 * verlet_list)[non_zero], param['vdw_sigma'], param['vdw_epsilon']) - cut_frc
	temp_xy = np.zeros(pair_dist.shape)
	
	for i in range(2):
		temp_xy[i][non_zero] += nonbond_frc * (pair_dist[i][non_zero] / pair_r2[non_zero])
		for j in range(2):
			virial_tensor[i][j] += np.sum((temp_xy[i] * pair_dist[i] * pair_dist[j])[virial_indicies])

	f_beads_x += np.sum(temp_xy[0], axis=0)
	f_beads_y += np.sum(temp_xy[1], axis=0)

	frc_beads = np.transpose(np.array([f_beads_x, f_beads_y]))
	
	return pot_energy, frc_beads, virial_tensor


def velocity_verlet_alg(pos, vel, frc, virial_tensor, param, pos_indices, bond_indices, frc_indices, angle_indices, 
				angle_bond_indices, vdw_coeff, virial_indicies, dt, sqrt_dt, cell_dim, NPT=False):
	"""
	velocity_verlet_alg(pos, vel, frc, virial_tensor, param, bond_matrix, vdw_matrix, verlet_list, bond_beads, dist_index, 
			r_index, dt, sqrt_dt, cell_dim, NPT=False, P_0 = 1, lambda_p = 1E-5)

	Integrate positions and velocities through time using verlocity verlet algorithm

	Parameters
	----------

	pos:  array_like (float); shape=(n_bead, n_dim)
		Positions of n_bead beads in n_dim

	vel: array_like, dtype=float
		Velocity of each bead in all collagen fibrils

	frc: array_like, dtype=float
		Forces acting upon each bead in all collagen fibrils

	virial_tensor:  array_like (float); shape=(n_dim, n_dim)
		Virial term of pressure tensor components
 
	bond_matrix: array_like (int); shape=(n_bead, n_bead)
		Matrix determining whether a bond is present between two beads

	verlet_list: array_like, dtype=int
		Matrix determining whether two beads are within rc radial distance

	bond_beads:  array_like, (int); shape=(n_angle, 3)
		Array containing indicies in pos array all 3-bead angular interactions

	dist_index:  array_like, (int); shape=(n_bond, 2)
		Array containing indicies in dx and dy arrays of all bonded interactions

	r_index:  array_like, (int); shape=(n_bond, 2)
		Array containing indicies in r array of all bonded interactions

	dt:  float
		Length of time step

	sqrt_dt:  float
		Sqare root of time step

	cell_dim: array_like, dtype=float
		Array with simulation cell dimensions

	vdw_param: array_like, dtype=float
		Parameters of van der Waals potential (sigma, epsilon)

	NPT:  

	
	Returns
	-------

	pos:  array_like (float); shape=(n_bead, n_dim)
		Updated positions of n_bead beads in n_dim

	vel: array_like, dtype=float
		Updated velocity of each bead in all collagen fibrils

	frc: array_like, dtype=float
		Updated forces acting upon each bead in all collagen fibrils

	verlet_list: array_like, dtype=int
		Matrix determining whether two beads are within rc radial distance

	pot_energy:  float
		Total energy of simulation

	virial_tensor:  array_like (float); shape=(n_dim, n_dim)
		Virial term of pressure tensor components

	"""

	beta = np.random.normal(0, 1, (param['n_bead'], param['n_dim']))
	vel += frc / param['mass'] * dt

	if NPT:
		kin_energy = ut.kin_energy(vel, param['mass'], param['n_dim'])
		P_t = 1 / (np.prod(cell_dim) * param['n_dim']) * (kin_energy - 0.5 * np.sum(np.diag(virial_tensor)))
		mu = (1 + (param['lambda_p'] * (P_t - param['P_0'])))**(1./3) 

	d_vel = param['sigma'] * beta - param['gamma'] * vel
	pos += (vel + 0.5 * d_vel) * dt
	vel += d_vel

	if NPT:
		pos = mu * pos
		cell_dim = mu * cell_dim

	cell = np.tile(cell_dim, (param['n_bead'], 1)) 
	pos += cell * (1 - np.array((pos + cell) / cell, dtype=int))

	distances = ut.get_distances(pos, cell_dim)
	r2 = np.sum(distances**2, axis=0)
	
	pot_energy, frc, virial_tensor = calc_energy_forces(pos, cell_dim, pos_indices, bond_indices, frc_indices, 
							angle_indices, angle_bond_indices, vdw_coeff, virial_indicies, param)

	return pos, vel, frc, cell_dim, pot_energy, virial_tensor, r2


def velocity_verlet_alg_mpi(pos, vel, frc, virial_tensor, param, pos_indices, bond_indices, frc_indices, angle_indices, 
				angle_bond_indices, vdw_coeff, virial_indicies, dt, sqrt_dt, cell_dim, comm, size, rank, NPT=False):
	"""
	velocity_verlet_alg(pos, vel, frc, virial_tensor, param, bond_indices, angle_indices, 
			angle_bond_indices, vdw_mat, vdw_indices, virial_indicies, dt, sqrt_dt, cell_dim, NPT=False, P_0 = 1, lambda_p = 1E-5)

	Integrate positions and velocities through time using verlocity verlet algorithm

	Parameters
	----------

	pos:  array_like (float); shape=(n_bead, n_dim)
		Positions of n_bead beads in n_dim

	vel: array_like, dtype=float
		Velocity of each bead in all collagen fibrils

	frc: array_like, dtype=float
		Forces acting upon each bead in all collagen fibrils

	virial_tensor:  array_like (float); shape=(n_dim, n_dim)
		Virial term of pressure tensor components
 
	bond_matrix: array_like (int); shape=(n_bead, n_bead)
		Matrix determining whether a bond is present between two beads

	verlet_list: array_like, dtype=int
		Matrix determining whether two beads are within rc radial distance

	bond_beads:  array_like, (int); shape=(n_angle, 3)
		Array containing indicies in pos array all 3-bead angular interactions

	dist_index:  array_like, (int); shape=(n_bond, 2)
		Array containing indicies in dx and dy arrays of all bonded interactions

	r_index:  array_like, (int); shape=(n_bond, 2)
		Array containing indicies in r array of all bonded interactions

	dt:  float
		Length of time step

	sqrt_dt:  float
		Sqare root of time step

	cell_dim: array_like, dtype=float
		Array with simulation cell dimensions

	vdw_param: array_like, dtype=float
		Parameters of van der Waals potential (sigma, epsilon)

	NPT:  

	
	Returns
	-------

	pos:  array_like (float); shape=(n_bead, n_dim)
		Updated positions of n_bead beads in n_dim

	vel: array_like, dtype=float
		Updated velocity of each bead in all collagen fibrils

	frc: array_like, dtype=float
		Updated forces acting upon each bead in all collagen fibrils

	verlet_list: array_like, dtype=int
		Matrix determining whether two beads are within rc radial distance

	pot_energy:  float
		Total energy of simulation

	virial_tensor:  array_like (float); shape=(n_dim, n_dim)
		Virial term of pressure tensor components

	"""

	if rank == 0: beta = np.random.normal(0, 1, (param['n_bead'], param['n_dim']))
	else: beta = None
	beta = comm.bcast(beta, root=0)

	vel += frc / param['mass'] * dt

	if NPT:
		kin_energy = ut.kin_energy(vel, param['mass'], param['n_dim'])
		P_t = 1 / (np.prod(cell_dim) * param['n_dim']) * (kin_energy - 0.5 * np.sum(np.diag(virial_tensor)))
		mu = (1 + (param['lambda_p'] * (P_t - param['P_0'])))**(1./3) 

	d_vel = param['sigma'] * beta - param['gamma'] * vel
	pos += (vel + 0.5 * d_vel) * dt
	vel += d_vel

	if NPT:
		pos = mu * pos
		cell_dim = mu * cell_dim

	cell = np.tile(cell_dim, (param['n_bead'], 1)) 
	pos += cell * (1 - np.array((pos + cell) / cell, dtype=int))
	
	pot_energy, frc, virial_tensor = calc_energy_forces(pos, cell_dim, pos_indices, bond_indices, frc_indices, 
							angle_indices, angle_bond_indices, vdw_coeff, virial_indicies, param)

	pot_energy = np.sum(comm.gather(pot_energy, root=0))
	frc = comm.allreduce(frc, op=MPI.SUM)
	virial_tensor = comm.allreduce(virial_tensor, op=MPI.SUM)

	return pos, vel, frc, cell_dim, pot_energy, virial_tensor
