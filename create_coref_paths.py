#!/usr/bin/env python
# -*- coding: utf8 -*-

import sys
import re
import argparse
import os
from amr_utils import *
from var_free_amrs import delete_wiki, single_line_convert

'''Script that converts the AMRs to a single line, taking care of re-entrancies in a nice way
   It does this by adding the absolute or relative paths. Currently, only absolute paths are implemented.
   Method is described in "Dealing with Co-reference in Neural Semantic Parsing", Van Noord and Bos, 2017
   
  Sample input:

   # ::snt Bob likes himself.

   (l / like
		:ARG0 (p / person :name "Bob")
		:ARG1 p)

   Sample output *.tf:

	(like :ARG0 (person :name "Bob") :ARG1 ( { :ARG0 |1| } ))

   Sample output *.sent:

	Bob likes himself.'''


def create_arg_parser():
	'''Create argument parser'''
	
	parser = argparse.ArgumentParser()
	parser.add_argument("-f", required=True, type=str, help="directory that contains the amrs")
	parser.add_argument('-output_ext', required = False, default = '.tf', help="extension of output AMR files (default .tf)")
	parser.add_argument('-sent_ext', required=False, default='.sent', help="extension of sentences (default .sent)")
	parser.add_argument('-p', required = True, action='store', choices=['rel','abs'], help='Add relative or absolute path?')	#currently only abs is implemented
	args = parser.parse_args()
	
	return args	


def replace_coreference(one_line_amrs, sents):
	'''Function that replaces coreference entities by its relative or absolute path
	   Also normalizes the input, references to variables can not be before instantiation'''
	
	new_amrs   = []
	coref_amrs = []
	path_dict  = {}
	
	amrs = [x.replace('(',' ( ').replace(')',' ) ').split() for x in one_line_amrs]	# "tokenize" AMRs
	no_var_list = ['interrogative','expressive','imperative']						# we always skip stuff such as :mode interrogative as possible variables
	
	for count, spl in enumerate(amrs):
		var_dict = get_var_dict(spl)	#find the path for each variable, save in dict								
		
		cur_path  = []
		all_paths = []
		new_spl   = []
		vars_seen = []
		level, previous_open, previous_close, added_var = 0, False, False, False
		
		for idx in range(1, len(spl)):	#skip first parenthesis to make things easier, add later
			new_spl.append(spl[idx])	#add all parts, if it is a variable and needs changing we do that later
			
			if idx == (len(spl) -1):	#skip last item, never coreference variable
				continue
			
			var_check, vars_seen = variable_match(spl, idx, no_var_list, vars_seen) 		#check if entity looks like a coreference variable
			
			if spl[idx] == '(':		#opening parenthesis, means we have to add the previous argument to our path
				level += 1
				cur_path, all_paths = find_cur_path_addition(cur_path, spl, idx, all_paths)	
				previous_close = False
			
			elif spl[idx] == ')':	#closing, decrease level by 1
				level -= 1
				previous_close = True
			
			elif previous_close:	#we previously saw a closing parenthesis, means we have finished the last part of our path	
				cur_path = cur_path[0:level]
				previous_close = False
				
			elif var_check:			#boolean that checked whether it is a variable
				previous_close = False
				
				if not (spl[idx].startswith(':') or spl[idx].startswith('"')):	#not a relation or value, often re-entrancy, check whether it exists
					if spl[idx] in var_dict:									#found variable, check paths here
						path_dict, all_paths, new_spl = add_path_to_amr(spl, idx, vars_seen, var_dict, cur_path, count, path_dict, all_paths, new_spl, coref_amrs)
				
			else:
				previous_close = False			#we saw a non-interesting entity, just continue	
		
		new_line = '(' + " ".join(new_spl)
		new_line = reverse_tokenize(new_line)	#reverse tokenization process of AMRs regarding parentheses
			
		new_amrs.append(new_line)
	
	assert len(amrs) == len(new_amrs)	#check if everything is still correct length
	
	print_coref_stats(coref_amrs, amrs, new_amrs, path_dict)	
	
	return new_amrs


def get_var_dict(spl):
	'''Function that returns a dictionary with all variable and their absolute path for an AMR'''
	
	cur_path = []
	level = 0
	all_paths = []
	var_dict = dict()
	previous_open = False
	previous_close = False
	
	for idx in range(1, len(spl)):	#skip first parenthesis
		if spl[idx] == '(':
			level += 1
			cur_path, all_paths = find_cur_path_addition(cur_path, spl, idx, all_paths)
			previous_close = False
		
		elif spl[idx] == ')':
			level -= 1
			previous_close = True
		
		elif spl[idx] == '/':
			var_name  = spl[idx-1]				#var found
			var_value =	spl[idx+1]
			if var_name not in var_dict:
				var_dict[var_name] = [var_value, " ".join(cur_path)]
			previous_close = False
		
		elif previous_close:		
			cur_path = cur_path[0:level]
			previous_close = False
		
		else:
			previous_close = False
	
	return var_dict		


def variable_match(spl, idx, no_var_list, vars_seen):
	'''Function that matches entities that are variables'''
	if spl[idx+1] == '/':
		vars_seen.append(spl[idx])
		return False, vars_seen
 	elif (not (spl[idx-1] == '/') and any(char.isalpha() for char in spl[idx]) and spl[idx] not in no_var_list):
		return True, vars_seen
	else:
		return False, vars_seen	


def find_cur_path_addition(cur_path, spl, idx, all_paths):
	'''Function that finds what we have to add to our current path'''
	
	counter = 1
	found_before = False
	for c in range(15,1,-1):
		to_add = "".join(cur_path) + spl[idx-1] + '|{0}|'.format(c)		#if there are multiple occurences, add the next one (2,3,4,5 etc)
		if to_add in all_paths:
			counter = c
			found_before = True
			break
		prev_add = to_add	
	
	if not found_before:
		counter = 1
	
	cur_path.append(spl[idx-1] + '|{0}|'.format(counter))
	all_paths.append(prev_add)
	
	if len(all_paths) != len(set(all_paths)):
		print 'Something is wrong'
	
	return cur_path, all_paths


def replace_variables(amrs):
	new_amrs = []
	for a in amrs:
		add_enter = re.sub(r'(:[a-zA-Z0-9-]+)(\|\d\|)',r'\1 \2',a)
		deleted_var_string = re.sub(r'\((.*?/)', '(', add_enter).replace('( ', '(')
		new_amrs.append(deleted_var_string)
	return new_amrs		


def add_path_to_amr(spl, idx, vars_seen, var_dict, cur_path, count, path_dict, all_paths, new_spl, coref_amrs):
	'''Function that finds the path that needs to be added and adds it'''
	
	if spl[idx-1].startswith(':'):							#we skipped this part of the path because it doesn't start with a parenthesis, still add it here
		cur_path, all_paths = find_cur_path_addition(cur_path, spl, idx, all_paths)
		
	if args.p == 'rel':
		raise NotImplementedError("Relative paths are not implemented yet")
	else:
		new_spl[-1] = '{ ' + var_dict[spl[idx]][1]	+ ' }'		#add absolute path here
		add_path = var_dict[spl[idx]][1]
		
		if not coref_amrs or coref_amrs[-1] != count:			#check if we already added this AMR
			coref_amrs.append(count)
		
		path_dict = add_to_dict(path_dict, add_path, 1)
	
	return path_dict, all_paths, new_spl


def print_coref_stats(coref_amrs, amrs, new_amrs, path_dict):
	'''Print interesting statistics about coref parsing'''
	
	print 'Length of AMRs with coref: {0}'.format(len(coref_amrs))
	
	total, once, max_len = 0, 0, 0
	
	for key in path_dict:
		total += 1
		if path_dict[key] == 1:
			once += 1
		
		if len(key.split()) > max_len:
			max_len = len(key.split())
			long_path = key
	
	print 'Longest path: {0}\nOf length: {1}\n'.format(long_path, max_len)			
	print '{0} out of {1} are unique'.format(once, total)						


if __name__ == "__main__":
	args = create_arg_parser()
	
	print 'Processing file {0}'.format(args.f)
	
	amr_file_no_wiki 	= delete_wiki(args.f)
	single_amrs, sents 	= single_line_convert(amr_file_no_wiki)
	repl_amrs  			= replace_coreference(single_amrs, sents)
	final_amrs 			= replace_variables(repl_amrs)
	
	out_f = args.f + args.output_ext
	out_f_sents = args.f + args.sent_ext
	
	write_to_file(final_amrs, out_f)
	write_to_file(sents, out_f_sents)
