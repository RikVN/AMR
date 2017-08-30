#!/usr/bin/env python
# -*- coding: utf8 -*-

import sys,re,argparse, os
from amr_utils import *

'''Scripts that sets input files in char-level 
   Possible to keep structure words as single "char", e.g. :domain, :ARG1, :mod, etc
   Is able to handle POS-tags in data - processing them as a single entity
   
   Input should be one AMR or sentence per line
   
   Sample input (AMR file):
   
   (establish-01 :ARG1 (model :mod (innovate-01 :ARG1 (industry))))
   
   Sample output (AMR file):
   
   ( e s t a b l i s h - 0 1 + :ARG1 + ( m o d e l + :mod + ( i n n o v a t e - 0 1 + :ARG1 + ( i n d u s t r y ) ) ) )'''


def create_arg_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument("-f", required=True, type=str, help="Input AMR file")
	parser.add_argument("-sent_ext", default = '.sent',  required=False, type=str, help="Input extension of AMRs (default .sent)")
	parser.add_argument("-amr_ext", default = '.tf', required=False, type=str, help="Output extension of AMRs (default .tf)")
	parser.add_argument('-s', action='store_true', help='Adding super characters for AMR files')
	parser.add_argument('-c', action='store_true', help='If there is path-coreference or index-coreference in the input')
	parser.add_argument('-pos', action='store_true', help='Whether input is POS-tagged')
	args = parser.parse_args()

	return args

def get_fixed_lines(file_lines):
	'''Fix lines, filter out non-relation and put back coreference paths'''
	
	fixed_lines = []
				
	for line in file_lines:
		spl = line.split()
		for idx, item in enumerate(spl):
			if len(item) > 1 and item[0] == ':':
				if any(x in item for x in [')','<',')','>','/','jwf9X']):		#filter out non-structure words, due to links etc
					new_str = ''
					for ch in item:
						new_str += ch + ' '
					spl[idx] = new_str.strip()
		fixed_lines.append(" ".join(spl))
	
	### Step that is coreference-specific: change | 1 | to |1|, as to not treat the indexes as normal numbers, but as separate super characters
	### Also change * 1 * to *1* and * 1 2 * to *12*
	
	if args.c:				#if coreference tagged input
		new_lines = []
		for l in fixed_lines:
			new_l = re.sub(r'\| (\d) \|',r'|\1|', l)
			new_l = re.sub(r'\* (\d) \*',r'*\1*', new_l)		
			new_l = re.sub(r'\* (\d) (\d) \*',r'*\1\2*', new_l)
			new_lines.append(new_l)
		return new_lines	
	else:		
			
		return fixed_lines


def get_amr_lines(f_path):
	file_lines = []
	for line in open(f_path,'r'):
		line = line.replace(' ','+') #replace actual spaces with '+'
		new_l = ''
		add_space = True
		for idx, ch in enumerate(line):
			
			if ch == ':' and line[idx+1].isalpha():		#after ':' there should always be a letter, otherwise it is some URL probably and we just continue
				add_space = False
				new_l += ' ' + ch
			elif ch == '+':
				add_space = True
				new_l += ' ' + ch
			else:
				if add_space:
					new_l += ' ' + ch
				else:					#we previously saw a ':', so we do not add spaces
					new_l += ch	
		file_lines.append(new_l)
	
	return file_lines


def process_pos_tagged(f_path):
	'''Process a POS-tagged sentence file'''
	
	fixed_lines = []
	
	for line in open(f_path, 'r'):
		new_l = ''
		no_spaces = False
		line = line.replace(' ','+') #replace actual spaces with '+'
		
		for idx, ch in enumerate(line):
			if ch == '|':
				no_spaces = True	#skip identifier '|' in the data
				new_l += ' '
			elif ch == ':' and line[idx-1] == '|':	#structure words are also chunks
				no_spaces = True
			elif ch == '+':
				no_spaces = False
				new_l += ' ' + ch
			elif no_spaces:		#only do no space when uppercase letters (VBZ, NNP, etc), special case PRP$	(not necessary)
				new_l += ch
			else:
				new_l += ' ' + ch
		fixed_lines.append(new_l)
	
	return fixed_lines
	   
		
if __name__ == '__main__':		
	args = create_arg_parser()
	
	if args.f.endswith(args.amr_ext):				
		out_f =  args.f.replace(args.amr_ext, '.char' + args.amr_ext)
			
		if args.s:						#add super characters
			print 'AMR file, super characters'
			amr_lines  = get_amr_lines(args.f)
			fixed_lines = get_fixed_lines(amr_lines)
			write_to_file(fixed_lines, out_f)
		else:
			print 'AMR file, no super characters'
			os_call =  'sed -e "s/\ /+/g"  -e "s/./&\ /g" < {0} > {1}'.format(args.f, out_f)
			os.system(os_call)
	
	elif args.f.endswith(args.sent_ext):					#different approach for pos-tagged sentences
		out_f =  args.f.replace(args.sent_ext,'.char' + args.sent_ext)
			
		if args.pos:
			print 'Sentence file, POS-tagged'
			lines = process_pos_tagged(args.f)
			write_to_file(lines, out_f)
		else:
			print 'Sentence file, not POS-tagged'	#do normal char-level approach for sentence files
			os_call =  'sed -e "s/\ /+/g"  -e "s/./&\ /g" < {0} > {1}'.format(args.f, args.f.replace(args.sent_ext,'.char' + args.sent_ext))
			os.system(os_call)
