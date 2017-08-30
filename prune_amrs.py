#!/usr/bin/env python
# -*- coding: utf8 -*-

'''Script that removes duplicate output from output AMRs. Most code is from best_amr_permutation.py.
	It removes nodes with same argument + concept under the same parent. 
	Also removes nodes that occur three times or more, no matter the parent.

	Sample input:
	
	(e / establish-01 :ARG1 (m / model :mod (i / innovate-01 :ARG1 (i2 / industry) :ARG1 (i3 / industry) :ARG1 (i4 / industry))))
	
	Sample output:
	
	(e / establish-01 :ARG1 (m / model :mod (i / innovate-01 :ARG1 (i2 / industry))))
	
	ARG1 - industry node occurs 3 times and therefore gets pruned twice in this example.'''

	
import re,sys, argparse, os, random, collections, subprocess, json
reload(sys)
from amr_utils import *
from best_amr_permutation import *


def create_arg_parser():

	parser = argparse.ArgumentParser()
	parser.add_argument("-f", required = True, type=str, help="File with AMRs (one line)")
	parser.add_argument("-cut_off", default = 15, type=int, help="When to cut-off number of permutations")
	args = parser.parse_args()
	
	return args


def restore_variables(f, filtered_amrs):
	'''Restore the removed variables for the pruned file'''
	
	print 'After pruning, restore variables...'
	
	write_to_file(filtered_amrs, f + '.pruned_temp')	#write variable-less AMR to file
	
	os.system('python restoreAMR/restore_amr.py -f {0} -o {1}'.format(f + '.pruned_temp', f + '.pruned'))	#restore here
	os.system("rm {0}".format(f + '.pruned_temp'))			#remove temp file again


def prune_file(f):
	'''Prune input file for duplicate input'''
	
	
	filtered_amrs = []
	changed, invalid = 0, 0
	
	print 'First remove all variables...'
	
	for idx, line in enumerate(open(args.f,'r')):
		clean_line = re.sub(r'\([A-Za-z0-9-_~]+ / ',r'(', line).strip()		#delete variables
		
		if clean_line.count(':') > 1:		#only try to do something if we can actually permutate					
			
			permutations, keep_string1, all_perms = get_permutations(clean_line,1,'',[], 'prune', args.cut_off)	#get initial permutations
			keep_str = '(' + keep_string1
			final_string = get_best_perm(permutations,  keep_str, '', keep_str, all_perms, 'prune', args.cut_off)	#prune duplicate output here
			
			add_to = " ".join(create_final_line(final_string).split())								#create final AMR line
			clean_line = " ".join(clean_line.split())
			filtered_amrs.append(add_to)
			
			if add_to != clean_line:	#keep track of number of pruned AMRs
				changed += 1
		else:
			filtered_amrs.append(clean_line.strip())
	
	restore_variables(f, filtered_amrs)	#restore variables and write to file
	
	print 'Changed {0} AMRs by pruning'.format(changed)
	

if __name__ == '__main__':
	args = create_arg_parser()
	print 'Pruning {0}'.format(args.f)
	prune_file(args.f)

	
