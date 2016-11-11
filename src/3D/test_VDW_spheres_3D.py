import numpy as np
import scipy as sp
import random as rand
import utilities_3D as ut
import pytest

def test_setup():

	N = 5
	L = 20
	sig1 = 2

	pos, vel, frc = ut.setup(N, L, sig1)

    	assert len(pos) == N
	assert len(pos[0]) == 3
	assert len(vel) == N
	assert len(vel[0]) == 3
	assert len(frc) == N
	assert len(frc[0]) == 3

def test_rand_vector():

	assert len(ut.rand_vector(3)) == 3

def test_unit_vector():

	assert ut.unit_vector([3, 4, 5]) == [np.sqrt(9./50), np.sqrt(16./50), np.sqrt(0.5)]

def test_save_system():

	ut.save_system('/data/fl7g13/Collagen/test', np.zeros(10), np.zeros(10), np.zeros(10), 10, 5, 5, np.zeros(10))
	ut.save_system('/data/fl7g13/Collagen/test', np.ones((10, 20, 20)), np.ones((10, 20, 20)), np.ones((10, 20, 20)), 10, 5, 5, np.ones(10))
	pos, vel, frc, N, boxl, bsize, TYPE = ut.load_system('/data/fl7g13/Collagen/test')

	assert len(pos) == 10
