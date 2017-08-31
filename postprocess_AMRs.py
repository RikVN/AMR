#!/usr/bin/env python
# -*- coding: utf8 -*-

'''Script that tests given seq2seq model on given test data, also restoring and wikifying the produced AMRs

Input should either be a produced AMR -file or a folder to traverse. Outputs .restore, .pruned, .coref and .all files'''


import sys
import re
import argparse
import os
from amr_utils import *
import wikify_file
from multiprocessing import Pool


def create_arg_parser():
	### If using -fol, -f and -s are directories. In that case the filenames of the sentence file and output file should match (except extension)
	### If not using -fol, -f and -s are directories ###
	
	parser = argparse.ArgumentParser()
	parser.add_argument('-f', required = True ,help="File or folder to be post-processed")
	parser.add_argument('-s', default = '' ,help="Sentence file or folder, necessary for Wikification")
	
	parser.add_argument('-fol', action = 'store_true' ,help="Whether -f is a folder")
	parser.add_argument('-sent_ext', default = '.sent' ,help="Sentence file, necessary for Wikification - only needed when doing single file")
	parser.add_argument('-out_ext', default = '.seq.amr' ,help="Output directory when doing a file")
	parser.add_argument('-t', default = 16, type = int ,help="Maximum number of parallel threads")
	
	parser.add_argument('-c', default = 'dupl', action='store', choices=['dupl','index','abs'], help='How to handle coreference - input was either duplicated/indexed/absolute path')
	parser.add_argument('-no_wiki', action='store_true', help='Not doing Wikification, since it takes a long time')
	args = parser.parse_args() 

	return args	


def check_valid(restore_file, rewrite):
	'''Checks whether the AMRS in a file are valid, possibly rewrites to default AMR'''
	
	idx = 0
	warnings = 0
	all_amrs = []
	for line in open(restore_file,'r'):
		idx += 1
		if not valid_amr(line):
			print 'Error or warning in line {0}, write default\n'.format(idx)
			warnings += 1
			default_amr = get_default_amr()
			all_amrs.append(default_amr)		## add default when error
		else:
			all_amrs.append(line)	
	
	if warnings == 0:
		print 'No badly formed AMRs!\n'
	elif rewrite:
		print 'Rewriting {0} AMRs with error to default AMR\n'.format(warnings)
		
		with open(restore_file,'w') as out_f:
			for line in all_amrs:
				out_f.write(line.strip()+'\n')
		out_f.close()		
	else:
		print '{0} AMRs with warning - no rewriting to default\n'.format(warnings)	
	

def add_wikification(in_file, sent_file):
	'''Function that adds wiki-links to produced AMRs'''
	
	wiki_file = in_file + '.wiki'
	
	print 'Doing Wikification...'
	
	if not os.path.isfile(wiki_file):	#check if wiki file doesn't exist already
		wikify_file.wikify_file(in_file, sent_file)
		
		if len([x for x in open(sent_file,'r')]) != len([x for x in open(wiki_file,'r')]):
			print 'Wikification failed for some reason (length {0} instead of {1})\n\tSave file as backup with wrong extension, no validating\n'
			os.system('mv {0} {1}'.format(wiki_file, wiki_file.replace('.wiki','.failed_wiki')))
			return wiki_file, False
		
		else:
			print 'Validating Wikified AMRs...\n'
			check_valid(wiki_file, True)
		
			return wiki_file, True
	else:
		print 'Wiki file already exists, skipping...'
		return wiki_file, True


def add_coreference(in_file, ext):
	'''Function that adds coreference back for each concept that occurs more than once'''
	
	print 'Adding coreference...\n'
	coref_file = in_file + ext
	
	if not os.path.isfile(coref_file):
		os.system('python restore_duplicate_coref.py -f {0} -output_ext {1}'.format(in_file, ext))
	else:
		print 'Coref file already exists, skipping...'	
		
	return coref_file
	

def do_pruning(in_file):
	'''Function that prunes duplicate output'''
	
	print 'Pruning...\n'
	prune_file = in_file + '.pruned'
	
	if not os.path.isfile(prune_file):
		os.system('python prune_amrs.py -f {0}'.format(in_file))
		print 'Validating pruned AMRs...\n'
		check_valid(prune_file, True)
	else:
		print 'Prune file already exists, skipping'	
		
	return prune_file


def restore_amr(in_file, out_file, coref_type):
	'''Function that restores variables in output AMR'''
	
	print 'Restoring variables...'
	
	if not os.path.isfile(out_file):
		if coref_type == 'index':
			restore_call = 'python restoreAMR/restore_amr.py -f {0} -o {1} -index'.format(in_file, out_file)
		elif coref_type == 'abs':
			restore_call = 'python restoreAMR/restore_amr.py -f {0} -o {1} -abs'.format(in_file, out_file)
		else:	
			restore_call = 'python restoreAMR/restore_amr.py -f {0} -o {1}'.format(in_file, out_file)
		os.system(restore_call)
		
		print 'Validating restored AMRs...\n'					
		check_valid(out_file, True)
	else:
		print 'Restore file already exists, skipping...'	
	
	return out_file


def process_file(input_list):
	'''Postprocessing AMR file'''
	f = input_list[0]
	sent_file = input_list[1]
	
	if not os.path.isfile(sent_file) or not os.path.isfile(f):
		print 'Something is wrong, sent-file or amr-file does not exist'
		sys.exit(0)
	
	if os.path.getsize(f) > 0: #check if file has content			
		restore_file 		= f + '.restore'
		restore_file 		= restore_amr(f, restore_file, args.c)
		prune_file 			= do_pruning(restore_file)
		
		if args.c == 'dupl':	#coreference by duplication is done in separate script
			coref_file 		= add_coreference(restore_file, '.coref')
		
		if not args.no_wiki:	#sometimes we don't want to do Wikification because it takes time
			wiki_file, success 	= add_wikification(restore_file, sent_file)
			
			#then add all postprocessing steps together, starting at the pruning
		
			print 'Do all postprocessing steps...\n'
			 
			wiki_file_pruned, success = add_wikification(prune_file, sent_file)
			
			if success:
				if args.c == 'dupl':
					coref_file_wiki_pruned 	  = add_coreference(wiki_file_pruned, '.coref.all')
				else:	#we already did coreference in restore file, still call the output-file .coref.all to not get confused in evaluation, just copy previous file
					os.system("cp {0} {1}".format(wiki_file_pruned, wiki_file_pruned + '.coref.all'))	
			else:
				print 'Wikification failed earlier, not trying again here\n'	
		print 'Done processing!'			


def match_files_by_name(amr_files, sent_files):
	'''Input is a list of both amr and sentence files, return matching pairs to test in parallel in the main function'''
	
	matches = []
	
	for amr in amr_files:
		match_amr = amr.split('/')[-1].split('.')[0]	#return filename when given file /home/user/folder/folder2/filename.txt
		for sent in sent_files:
			match_sent = sent.split('/')[-1].split('.')[0]
			if match_sent == match_amr:		#matching sentence and AMR file, we can process those
				matches.append([amr, sent])
				break
	
	return matches
	
				
if __name__ == "__main__":
	args = create_arg_parser()
	
	if not args.fol:
		print 'Process single file\n'
		process_file(args.f, args.s)
	else:
		sent_files = get_files_by_ext(args.s, args.sent_ext)
		amr_files  = get_files_by_ext(args.f, args.out_ext)
		matching_files = match_files_by_name(amr_files, sent_files)
		
		#Process file in parallel here
		print 'Processing {0} files, doing max {1} in parallel'.format(len(matching_files), args.t)
		
		pool = Pool(processes=args.t)						
		pool.map(process_file, matching_files)	
	
	

