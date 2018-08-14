"""
ColECM: Collagen ExtraCellular Matrix Simulation
MAIN ROUTINE 

Created by: Frank Longford
Created on: 01/11/2015

Last Modified: 31/12/2018
"""

import sys, os
import utilities as ut

current_dir = os.getcwd()
dir_path = os.path.dirname(os.path.realpath(__file__))

modules = []

if ('simulation' in sys.argv): modules.append('simulation') 
if ('analysis' in sys.argv): modules.append('analysis')
if ('editor' in sys.argv): modules.append('editor')
if ('learning' in sys.argv): modules.append('learning')
if ('speed' in sys.argv): modules.append('speed')
if ('experimental' in sys.argv): modules.append('experimental')

ut.logo()

if len(modules) == 0: modules = (input(' Please enter desired modules to run (SIMULATION and/or ANALYSIS or EDITOR): ').lower()).split()

if ('-input' in sys.argv): input_file_name = current_dir + '/' + sys.argv[sys.argv.index('-input') + 1]
else: input_file_name = False

if ('simulation' in modules):
	from simulation import simulation
	simulation(current_dir, input_file_name)
if ('analysis' in modules):
	from analysis import analysis
	analysis(current_dir, input_file_name)
if ('editor' in modules):
	from editor import editor
	editor(current_dir, input_file_name)
if ('learning' in modules):
	from machine_learning import learning
	learning(current_dir)
if ('speed' in modules):
	from simulation import speed_test
	speed_test(current_dir, input_file_name)
if ('experimental' in modules):
	from experimental_image import experimental_image
	if ('-all' in sys.argv):
		input_files = os.listdir(current_dir)
		for input_file_name in input_files:
			if input_file_name.endswith('.tif'): 
				experimental_image(current_dir, input_file_name)
	elif ('-name' in sys.argv):
		input_file_name = sys.argv[sys.argv.index('-name') + 1]
		experimental_image(current_dir, input_file_name)
