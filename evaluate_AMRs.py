#!/usr/bin/env python

import os
import re
import sys
import subprocess
import argparse
import random
import json
from multiprocessing import Pool
import datetime
import multiprocessing

'''Script that does SMATCH in parallel and prints ordered output per epoch, per file and per type (extension) to the screen'''


def create_arg_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument('-g', required=True, type=str, help="Folder with gold AMR files")
	parser.add_argument('-p', required = True, help = 'Root folder to check for output results')
	parser.add_argument('-mx', required=False, type=int, default = 12, help="Max number of parallel threads (default 12)")
	parser.add_argument('-rs', required=False, type=int, default = 6, help="Number of restarts for smatch (default 6)")
	parser.add_argument('-gold_ext', default = '.txt', type=str, help="Ext of produced files (default .txt)")
	parser.add_argument('-type', required = True, action='store', choices=['all','comb','rest','prune','coref','wiki'], help='Output choices - only do certain extensions')
	parser.add_argument('-force', action='store_true', help='If used, reprocess anyway even though results are in dict (e.g. with more restarts)')
	parser.add_argument('-res_dict', default = 'res_dict.txt', type=str, help="Dictionary for saving/loading results")
	parser.add_argument('-out_ext', default = '.seq.amr', type=str, help="Extension of output files (before restoring, default .seq.amr)")
	parser.add_argument('-smatch', default = 'smatch/smatch_edited.py', type=str, help="Smatch file we use for testing - edited to handle one-line input")
	parser.add_argument('-inp', default = 'prod', choices = ['no', 'prod','gold','both'], type=str, help="If the input is in one-line format (default prod)")
	args = parser.parse_args()

	return args


def ids_to_check(in_type, out_ext):	
	if in_type == 'rest':
		ids = [out_ext + '.restore']
	elif in_type == 'comb':
		ids = [out_ext + '.restore', out_ext + '.restore.wiki', out_ext + '.restore.coref', out_ext + '.restore.pruned', out_ext + '.restore.pruned.wiki.coref.all']
	elif in_type == 'all':
		ids = [out_ext + '.restore.pruned.wiki.coref.all']	
	elif in_type == 'coref':
		ids = [out_ext + '.restore.coref']
	elif in_type == 'wiki':
		ids = [out_ext + '.restore.wiki']	
	elif in_type == 'prune':
		ids = [out_ext + '.restore.pruned']			
	
	return ids
	

def get_res_dict(dict_file, force):
	'''Load existing results dict or make a new one. If force = True, recalculate anyway'''
	
	if os.path.isfile(dict_file) and not force:
		with open(dict_file, 'r') as in_f:
			res_dict = json.load(in_f)
		in_f.close()
		
		print 'Read in dict with len {0}'.format(len(res_dict))
		
	else:	
		res_dict = {}
		print 'Started testing from scratch'	
	
	return res_dict		


def do_smatch(arg_list):
	'''Runs the smatch OS call, return results to save later'''
	os_call, identifier, match_part = arg_list[0], arg_list[1], arg_list[2]
	
	output = subprocess.check_output(os_call, shell=True)
	f_score = output.split()[-1]		# get F-score from output
		
	return [f_score, identifier, match_part]


def print_nice_output(res_dict):
	'''Print nice output to terminal'''
	
	print 'Results:\n'
	
	print_list = []
	print_rows = []
	file_ids = []
	
	### Set up rows for printing ###
	
	for r in res_dict:					#get file ids
		for item in res_dict[r]:
			if item[0] not in file_ids:
				file_ids.append(item[0])
	
	sorted_ids = sorted(file_ids)
	print_rows.append([0,''] + sorted_ids)
	
	for r in res_dict:
		print_list = [int(r.split()[0]), r]
		for s in sorted_ids:
			added = False
			for item in res_dict[r]:					## test file options
				if s == item[0]:
					print_list.append(str(item[1]))
					added = True
			if not added:
				print_list.append('NA')		
		print_rows.append(print_list)					
	
	### Sort rows on epochs, extensions and actually print in a nice way ###
	
	sorted_r = sorted(print_rows, key = lambda x : x[0:2]) 		#sort by number of epochs
	all_sorted_rows = [x[1:] for x in sorted_r]					#remove epoch from to be printed stuff
	col_widths = []
	
	sorted_rows = [x for x in all_sorted_rows if len(x) == max([len(y) for y in all_sorted_rows])]	#only keep rows that have F-scores (and thus have max length)
	
	for idx in range(len(sorted_rows[0])):					#for nice printing, calculate max column length
		col_widths.append(max([len(x[idx]) for x in sorted_rows]) + 1)
	
	for idx, row in enumerate(sorted_rows):					#print rows here, adjusted for column width
		print " ".join(word.ljust(col_widths[col_idx]) for col_idx, word in enumerate(row))
	


def update_res_dict(res_dict, results):
	
	for res in results:			#contains [f_score, identifier, match_part]
		if res[1] in res_dict:
			res_dict[res[1]].append([res[2], res[0]])
		else:
			res_dict[res[1]] = [[res[2], res[0]]]	
	
	return res_dict		


def get_matching_ext(f, extensions):
	for ext in extensions:
		if f.endswith(ext):
			return ext
	
	return 'No ext'		


def get_gold_file(f, gold_files):
	'''Function that matches produced and gold files
	   If file is /folder/folder2/file-idhere.amr, we want to match idhere'''
	
	match_f = f.split('.')[0].split('-')[-1]
	
	for g in gold_files:
		match_g = g.split('/')[-1].split('.')[0].split('-')[-1]
		if match_f == match_g:
			return g, match_g
	
	return '',''		


def check_dict(identifier, match_part, res_dict):
	'''Function that checks if this specific file is already done for this epoch'''
	
	if identifier not in res_dict:
		return True
	else:
		for item in res_dict[identifier]:
			if item[0] == match_part:	#matching part of the file here, e.g. return true is 'dev' or 'dfa' is already there for this identifier
				return False
	
	return True
		

def get_identifier(fol, matching_ext):
	'''Get identifier string for this file - e.g. 12 epochs (.seq.amr.restore)'''
	try:
		ep_num = re.findall(r'(ep|epoch|epochs|epo)([\d]+)', fol)[0]
		identifier = '{0} epochs ({1})'.format(ep_num[1], matching_ext)
		return identifier 
	except:
		return ''

		
if __name__ == '__main__':
	
	### do preprocessing and preparing ###
	
	args 	   = create_arg_parser()
	extensions = ids_to_check(args.type, args.out_ext)
	res_dict   = get_res_dict(args.res_dict, args.force)
	gold_files = [os.path.join(args.g, f) for f in os.listdir(args.g) if os.path.isfile(os.path.join(args.g, f)) and f.endswith(args.gold_ext)]	#get all gold files with correct extension
	
	### get smatch calls we want to do ###
	
	process_list = []
	
	for root, dirs, files in os.walk(args.p):	#loop over produced files
		for f in files:
			if f.endswith(tuple(extensions)):
				matching_ext 		= get_matching_ext(f, extensions)
				gold_f, match_part  = get_gold_file(f, gold_files)	#get gold file
				if gold_f:
					prod_f = os.path.join(root, f)
					identifier = get_identifier(prod_f, matching_ext)
					if identifier:
						if check_dict(identifier, match_part, res_dict):	#we did this before, no need now
							os_call = 'python {0} -r {1} --one_line {2} -f {3} {4}'.format(args.smatch, args.rs, args.inp, prod_f, gold_f)
							process_list.append([os_call, identifier, match_part])	#save smatch-calls in list to process in parallel later
					else:
						print 'Could not find identifier for {0}, skipping...'.format(prod_f)		
					
	### do smatch calls in parallel ###
	
	print 'Doing {0} smatch threads - max {1} in parallel'.format(len(process_list), args.mx)
	
	results = multiprocessing.Pool(args.mx).map(do_smatch, process_list)
	
	#### Print results and save them to file + dict ###
	
	res_dict = update_res_dict(res_dict, results)
	print_nice_output(res_dict)
	
	if res_dict:
		with open(args.res_dict, 'w') as out_f:	#save smatch results to dict
			json.dump(res_dict, out_f)
		out_f.close()	
		
