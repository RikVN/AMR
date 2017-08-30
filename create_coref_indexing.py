#!/usr/bin/env python
# -*- coding: utf8 -*-


'''Script that converts the AMRs to a single line, taking care of re-entrancies in a nice way by adding special characters

Sample input :

# ::snt Jack wants to buy ice-cream .
(w / want
	:ARG1 (p / person :name "Jack")
         :ARG3 (b / buy
             :ARG1 p
             :ARG2 (i / ice-cream)))

Sample output *.tf:

(want :ARG1 (*1* person :name "Jack") :ARG3 (buy :ARG1 *1* :ARG2 (ice-cream)))

Sample output *.sent:

Jack wants to buy ice-cream .'''

import sys
import re
import argparse
import os
from amr_utils import *
from var_free_amrs import delete_wiki, single_line_convert
from create_coref_paths import replace_variables


def create_arg_parser():

	parser = argparse.ArgumentParser()
	parser.add_argument("-f", required=True, type=str, help="File with AMRs")
	parser.add_argument('-output_ext', required = False, default = '.tf', help="extension of output AMR files (default .tf)")
	parser.add_argument('-sent_ext', required=False, default='.sent', help="extension of sentences (default .sent)")
	args = parser.parse_args()
	
	return args


def variable_match(spl, idx, no_var_list):
	'''Function that matches entities that are variables occurring for the second time'''
	if idx >= len(spl) or idx == 0:
		return False
	
 	if (not spl[idx-1] == '/' and any(char.isalpha() for char in spl[idx]) and spl[idx] not in no_var_list and not spl[idx].startswith(':') and len([x for x in spl[idx] if x.isalpha() or x.isdigit()]) == len(spl[idx]) and (len(spl[idx]) == 1 or (len(spl[idx]) > 1 and spl[idx][-1].isdigit()))):
		return True
	else:
		return False
		

def coreference_index(one_line_amrs, sents):
	'''Function that replaces coreference entities by its relative or absolute path'''
	
	new_amrs = []
	amrs = [x.replace('(',' ( ').replace(')',' ) ').split() for x in one_line_amrs]	# "tokenize" AMRs
	no_var_list = ['interrogative','expressive','imperative']						# we always skip stuff such as :mode interrogative as possible variables
	
	for count, spl in enumerate(amrs):						
		all_vars = []
		
		for idx in range(0, len(spl)):
			if variable_match(spl, idx, no_var_list): 		#check if entity looks like a coreference variable				
				all_vars.append(spl[idx])
		
		vars_seen = []
		new_spl = []	
		
		for idx in range(0, len(spl)):
			if variable_match(spl, idx, no_var_list): 		#check if entity looks like a coreference variable				
				if all_vars.count(spl[idx]) > 1:			#if entity occurs at least twice, make mention of it
					if spl[idx] in vars_seen:
						new_spl.append('*{0}*'.format(vars_seen.index(spl[idx])))	#add index-path here
					else:
						new_spl.append('*{0}*'.format(len(vars_seen)))
						vars_seen.append(spl[idx])
					 
			elif spl[idx] != '/':				#part of variable, skip
				new_spl.append(spl[idx])
		
		new_line = " ".join(new_spl)					
		new_line = reverse_tokenize(new_line)	#reverse the tokenization process		
		new_amrs.append(new_line)
	
	assert len(amrs) == len(new_amrs)

	return new_amrs	


if __name__ == "__main__":
	args = create_arg_parser()
	
	print 'Processing {0}'.format(args.f)
	
	amr_file_no_wiki 	= delete_wiki(args.f)
	single_amrs, sents 	= single_line_convert(amr_file_no_wiki)
	repl_amrs  			= coreference_index(single_amrs, sents)
	
	out_f = args.f + args.output_ext
	out_f_sents = args.f + args.sent_ext
	
	write_to_file(repl_amrs, out_f)
	write_to_file(sents, out_f_sents)
