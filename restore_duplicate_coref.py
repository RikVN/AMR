import sys
import re
import argparse
import os
from amr_utils import *


'''Script that adds coreference back in produced AMRs. It does this by simply replacing duplicate nodes by the reference to the variable of the first node.

Input needs to be in one-line format, with variables present.

Sample input:

(e / establish-01 :ARG1 (m / model :mod (i / innovate-01 :ARG1 (i2 / industry) :ARG1 (m2 / model) :ARG1 (i3 / innovate-01))))
	
Sample output:

(e / establish-01 :ARG1 (m / model :mod (i / innovate-01 :ARG1 (i2 / industry) :ARG1 m :ARG1 i)))'''


def create_arg_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument("-f", required=True, type=str, help="File that contains amrs / sentences to be processed")
	parser.add_argument("-output_ext", default = '.coref', required=False, type=str, help="Output extension of AMRs (default .coref)")
	args = parser.parse_args()
	
	return args


def process_var_line(line, f):
	'''Function that processes line with a variable in it. Returns the string without 
	   variables and the dictionary with var-name + var - value'''

	var_list = []
	curr_var_name, curr_var_value = False, False
	var_value , var_name = '', ''
	skip_first = True
	
	for idx, ch in enumerate(line):
		if ch == '/':				# we start adding the variable value
			curr_var_value = True
			curr_var_name = False
			var_value = ''
			continue
		if ch == '(':				# we start adding the variable name										
			curr_var_name = True
			curr_var_value = False
			if var_value and var_name:		#we already found a name-value pair, add it now
				if not var_list and skip_first:
					skip_first = False				#skip first entry, but only do it once. We never want to refer to the full AMR.
				else:	
					add_var_value = var_value.strip().replace(')','')
					var_list.append([var_name.strip(), add_var_value])
			var_name = ''
			continue	
		
		if curr_var_name:			# add to variable name
			var_name += ch
		elif curr_var_value:		# add to variable value
			var_value += ch
	
	var_list.append([var_name.strip(), var_value.strip().replace(')','')])	#add last one
	
	for item in var_list:
		try:
			if not item[1].split()[-1].isdigit() and len(item[1].split()) > 1:			#keep in :quant 5 as last one, but not ARG1: or :mod
				item[1] = " ".join(item[1].split()[0:-1])
		except:
			print 'Small error, just ignore: {0}'.format(item)	#should not happen often, but strange, unexpected output is always possible	
						
	return var_list


def process_file(f):

	coref_amrs = []
	
	for indx, line in enumerate(open(f,'r')):
		var_list = process_var_line(line, f)	#get list of variables and concepts
		new_line = line
		
		for idx in range(len(var_list)-1):
			for y in range(idx+1, len(var_list)):
				if var_list[idx][1] == var_list[y][1]:	#match - we see a concept we already saw before
					replace_item = var_list[y][0] + ' / ' + var_list[y][1]	#the part that needs to be replaced
					if replace_item in line:
						
						new_line_replaced = re.sub(r'\({0} / [^\(]*?\)'.format(var_list[y][0]), var_list[idx][0], new_line)		#coref matching, replace :ARG1 (var / value) by :ARG refvar
						
						if new_line_replaced != new_line: #something changed
							if valid_amr(new_line_replaced):	#only replace if resulting AMR is valid
								new_line = new_line_replaced	
					
		coref_amrs.append(new_line.strip())					
								
	assert(len(coref_amrs) == indx + 1)	#check if length is the same
	
	return coref_amrs

	
if __name__ == '__main__':
	args = create_arg_parser()
	
	coref_amrs = process_file(args.f)
	write_to_file(coref_amrs, args.f + args.output_ext)
