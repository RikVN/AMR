#!/usr/bin/env python
# -*- coding: utf8 -*-

import sys,re,os
import argparse
from random import shuffle
from amr_utils import *
from var_free_amrs import delete_wiki, delete_amr_variables, process_var_line, single_line_convert

'''Script that augments the data to get the best AMR permutation based on word order
   INPUT SHOULD INCLUDE ALIGNMENTS
   
   It outputs the normal variable-free AMR as well as the best AMR permutation. Each AMR on a single line.
   
   Sample input:
   
	# ::id PROXY_AFP_ENG_20071228_0377.18 ::amr-annotator SDL-AMR-09 ::preferred
	# ::tok Opium is the raw material used to make heroin .
	# ::alignments 0-1.2 1-1.2.r 3-1.1 4-1 5-1.3 7-1.3.1 8-1.3.1.1
	(m / material~e.4 
		  :mod (r / raw~e.3) 
		  :domain~e.1 (o / opium~e.0) 
		  :ARG1-of (u / use-01~e.5 
				:ARG2 (m2 / make-01~e.7 
					  :ARG1 (h / heroin~e.8) 
					  :ARG2 o)))
   
   Sample output best order (note that some nodes are swapped!):
   
   (material :domain (opium) :mod (raw) :ARG1-of (use-01 :ARG2 (make-01 :ARG2 (opium) :ARG1 (heroin))))
   
   Sample output sent:
	
   Opium is the raw material used to make heroin .'''	
	

def create_arg_parser():
	
	parser = argparse.ArgumentParser()
	parser.add_argument("-f", required=True, type=str, help="folder that contains to be processed files")
	parser.add_argument("-amr_ext", default = '.txt', type=str, help="AMR extension (default .txt) - should have alignments")
	parser.add_argument("-cut_off", default = 15, type=int, help="When to cut-off number of permutations")
	parser.add_argument("-double", action = 'store_true', help="Add best permutation AMR AND normal AMR?")
	args = parser.parse_args() 

	return args


def process_var_line(line, var_dict):
	'''Function that processes line with a variable in it. Returns the string without 
	   variables and the dictionary with var-name + var - value'''
	curr_var_name = False
	curr_var_value = False
	var_value = ''
	var_name = ''
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
				var_dict[var_name.strip()] = var_value.strip().replace(')','').replace(' :name','').replace(' :dayperiod','').replace(' :mod','')
			var_name = ''
			continue	
		
		if curr_var_name:		# add to variable name
			var_name += ch
		if curr_var_value:		# add to variable value
			var_value += ch

	var_dict[var_name.strip()] = var_value.strip().replace(')','')					
	deleted_var_string = re.sub(r'\((.*?/)', '(', line).replace('( ', '(')					# delete variables from line
	
	return deleted_var_string, var_dict


def get_tokenized_sentences(f):
	sents = [l.replace('# ::snt','').replace('# ::tok','').strip() for l in open(f,'r') if (l.startswith('# ::snt') or l.startswith('# ::tok'))]
	return sents


def remove_alignment(string):
	 '''Function that removes alignment information from AMR'''
	 string = re.sub('~e\.[\d,]+','', string)
	 return string


def get_word_and_sense(line):
	'''Character based extraction because I couldn't figure it out using regex'''
	
	quotes = 0
	adding = False
	comb = []
	word = ''
	if '"' in line:
		for idx, ch in  enumerate(line):
			if ch == '"':
				quotes += 1
				if quotes % 2 != 0:
					adding = True
				else:					# finished quotations
					comb.append([word])
					word = ''
					adding = False
			elif ch == '~':
				if adding:
					word += ch
				elif ':op' in "".join(line[idx-4:idx-1]):		#bugfix for strange constructions, e.g. name :op1~e.4 "Algeria"~e.2 
					continue	
				else:	
					if idx+4 < len(line):
						sense_line = line[idx+1] + line[idx+2] + line[idx+3] + line[idx+4]
					else:
						sense_line = line[idx+1] + line[idx+2] + line[idx+3]	
					sense = int("".join([s for s in sense_line if s.isdigit()]))
					try:
						comb[-1].append(sense)
					except:
						pass		
			else:
				if adding:
					word += ch
				else:
					continue
	elif ':op' not in line:
		return [['','']]
	else:
		try:
			tmp = line.split()[2]		
			sense, word = get_sense(tmp)
			comb = [[word,sense]]
		except:
			print 'Strange error that only happens for parses (non-gold data), ignore'
			return [['','']]			 
	return comb				


def get_sense(word):
	'''Function that gets the sense of a certain word in aligned AMR'''
	
	if '~' in word:
		sense = word.split('~')[-1].split('.')[-1] 		# extract 16 in e.g. house~e.16
		
		if ',' in sense:								# some amr-words refer to multiple tokens. If that's the case, we take the average for calculating distance
														# although this means that the actual sense does not refer to the tokens anymore (# e.g. the sense of house~e.4,12 becomes 8)			
			sense = round((float(sum([int(i) for i in sense.split(',')]))) / (float(len(sense.split(',')))),0)
		else:
			sense = int(sense)
														
		word = word.split('~')[0]							# remove sense information to process rest of the word
	else:
		sense = ''	
	
	return sense, word
	
				
def find_words(line):
	'''Finds all words in the AMR structure'''
	
	comb = []
	spl_line = line.split('(')
	if '(' not in line:
		if line.count('~') > 0 and len(line.split()) > 1:
			sense, word = get_sense(line.split()[1])
			return [[word, sense]]
		else:
			return [['none-found',0]]	
	else:	
		for idx in range(1, len(spl_line)):
			if spl_line[idx]:
				word = spl_line[idx].strip().split()[0].replace(')','')
				if word == 'name':											#name gets special treatment by AMRs
					cut_word = spl_line[idx].split(')')[0]
					comb += get_word_and_sense(cut_word)	
				else:	
					sense, word = get_sense(word)
					num_digits = sum(c.isdigit() for c in word)
					
					if word.count('-') == 1 and num_digits < 3 and num_digits > 0:				# tricky: we want to change break-01 to break, but do not want to screw up dates (08-09-2016 or 28-10)
						word = word.split('-')[0]
					comb.append([word,sense])
	
	for idx in range(len(comb)):
		if len(comb[idx]) < 2:
			comb[idx].append('')		#add empty sense
	
	return comb	


def matching_words(permutations):
	'''Finds all words in different order for all the permutations'''
	
	all_found = []
	
	for per in permutations:
		found_words = find_words(per)
		if found_words:
			all_found.append(find_words(per))
	
	return all_found		


def calc_distance(l):
	'''Calculates distance between list items in two lists'''
	
	#l needs to start from zero, get lowest number and substract it from all numbers
	
	min_l = min([x[1] for x in l if x != ''])
	l = [[x[0], (x[1] - min_l)] for x in l if x[1]!= '']

	distance = 0
	
	for idx, item in enumerate(l):
		if len(item) > 1 and item[1] != '':		#check if we found a sense
			diff = abs(item[1] - idx)			#check how far away we are in our token list
			distance += diff
			
	return distance

def calc_distance_full_amr(l):
	'''Calculates distance between list items in 2 two lists'''
	
	#l needs to start from zero, get lowerst number and substract it from all numbers
	
	distance = 0
	l = [x for x in l if (x[1] != '' and len(x) > 1)]
	
	sorted_l = sorted(l, key = lambda x:x[1])
	
	#calculate difference between where optimal position is (in sorted) and where the item is now
	
	for idx, item in enumerate(l):
		rank_sorted = sorted_l.index(item)
		diff = abs(idx - rank_sorted)
		distance += diff
			
	return distance		


def do_swap(w_list1, w_list2):
	'''Checks if we should swap two list items'''
	
	distance_now  = calc_distance(w_list1 + w_list2)
	distance_swap = calc_distance(w_list2 + w_list1)
	
	
	return distance_now > distance_swap			#true or false		


def filter_colons(part):
	'''Funtion to filter out timestamps (e.g. 08:30) and websites (e.g. http://site.com)'''

	new_parts = []
	split_part = part.split(':')
	for idx in range(0, len(split_part)):
		if idx == 0:
			new_parts.append(split_part[idx])
		
		elif split_part[idx][0].isalpha():
			new_parts.append(split_part[idx])
		else:
			new_parts[-1] += ':' + split_part[idx]		# not actually a new part, just add to last one
				
	return new_parts			


def get_add_string(search_part):
	'''Get the initial permutations and add_string'''
	
	paren_count = 0
	start_adding = False
	permutations = []	
	add_string = ''
	
	for idx, ch in enumerate(search_part):
		if ch == '(':					# parenthesis found
			if start_adding:
				add_string += ch
			paren_count += 1
		elif ch == ':':
			start_adding = True
			add_string += ch
		elif ch == ')':
			paren_count -= 1
			if start_adding:
				add_string += ch
			if paren_count == 0:		# we closed one of the permutations now
				permutations.append(add_string.strip())
				add_string = ''
		elif start_adding:
			add_string += ch				
	
	if add_string and ':' in add_string:
		permutations.append(add_string.replace(')','').strip())
		for idx, p in enumerate(permutations):
			while permutations[idx].count(')') < permutations[idx].count('('):
				permutations[idx] += ')'
	
	#permutate without brackets (e.g. :op1 "hoi" :op2 "hai" :op3 "ok"	
	
	for p in permutations:
		if ')' not in p or '(' not in p:				
			if p.count(':') > 2:
				p_split = p.split(':')[1:]
				new_perms = [':' + x.strip() for x in p_split]
				return add_string, new_perms
	
	
	return add_string, permutations			


def get_keep_string(new_parts, level):
	'''Obtain string we keep, it differs for level 1'''
	
	if level > 1:
		keep_string = ':' + ":".join(new_parts[:1])
	else:
		keep_string = ":".join(new_parts[:1])
	search_part = ':' + ":".join(new_parts[1:])
	
	return keep_string, search_part
	

def combine_permutations(permutations, cut_off):
	'''Combine permutations if they exceed the cut-off specified'''
	
	if len(permutations) > cut_off:
		shuffle(permutations)
		permutations = permutations[0:cut_off - 1] + [" ".join(permutations[cut_off - 1:])]	# just add extra permutations to the last permutation
	
	return permutations


def change_possible(part):
	'''Check if there is anything to permute'''
	
	if ':' not in part or (part.count(':') == 1 and ('http:' in part or 'https:' in part)):
		return False
	else:
		return True	

											
def get_permutations(part, level,  sent_amr, all_perms, type_script, cut_off):	
	'''Function that returns the permutations in the best order'''
	part = part[1:] 																			# make life easier by skipping first '(' or ':'
	sent_words = [w.lower() for w in sent_amr.split()]  										# get all words in sentence in lower case
	
	if not change_possible(part):	# if there is nothing to change then we return
		if level == 1:
			return [part], '', all_perms
		else:	
			return [':' + part], '', all_perms	

	new_parts 				 = filter_colons(part)												#remove non-arguments that have a colon such as timestamps and websites
	keep_string, search_part = get_keep_string(new_parts, level)
	add_string, permutations = get_add_string(search_part) 
	
	permutations = combine_permutations(permutations, cut_off)	
	word_list 	 = matching_words(permutations)													#find the list of lists that contain word-sense pairs
	
	#Two possibilities here, ordering or pruning. This script only does ordering, delete_double_args.py does pruning and uses this function.
	
	if type_script == 'prune':
		permutations_set = []
		
		for p in permutations:
			if p in permutations_set:		#remove all nodes with same parent
				continue
			elif p not in all_perms:
				permutations_set.append(p)
			elif all_perms.count(p) < 2:	#if we saw the node twice, stop adding
				permutations_set.append(p)
			all_perms.append(p)
		return permutations_set, keep_string, all_perms	
	
	else:
		if len(word_list)!= len(permutations):	#something strange is going on here, just ignore it and do nothing to avoid errors
			print 'Strange AMR part'
			all_perms += permutations
			return permutations, keep_string, all_perms													
		else:
			for p in range(len(permutations)):
				for idx in range(len(permutations)-1):
					if do_swap(word_list[idx], word_list[idx+1]):									#permuting takes place here, check if swapping results in better order
						permutations[idx], permutations[idx+1] = permutations[idx+1], permutations[idx]
						word_list[idx], word_list[idx+1] = word_list[idx+1], word_list[idx]			
			all_perms += permutations						
			return permutations, keep_string, all_perms		


def do_string_adjustments(permutations_new, keep_string2):
	add_string = keep_string2 + ' ' + " ".join(permutations_new) + ' '
	
	while add_string.count(')') < add_string.count('('): 			## check if we need to add a parenthesis
		add_string += ')' 											## avoid extra unnecessary space
	
	return add_string


def create_final_line(final_string):
	'''Do final adjustments for line'''
	
	add_to = final_string.replace('  ',' ') .strip()
	while ' )' in add_to:
		add_to = add_to.replace(' )',')')
	
	add_to = fix_paren(add_to)	
	add_to = remove_alignment(add_to)
	add_to = add_to.replace('):',') :').replace(' :)',')').replace(': :',':')	#fix some layout stuff
	
	return add_to
	
		
def fix_paren(string):
	while string.count('(') > string.count(')'):
		string += ')'
	return string	


def get_best_perm(permutations, keep_str, sent, final_string, all_perms, type_script, cut_off):
	
	'''This must also be possible recursive - I tried...'''
	
	
	for indx2, p2 in enumerate(permutations):
		permutations_2, keep_string2, all_perms = get_permutations(p2,2, sent, all_perms, type_script, cut_off)
		
		for indx3, p3 in enumerate(permutations_2):
			permutations_3, keep_string3, all_perms = get_permutations(p3,3, sent, all_perms, type_script, cut_off)
			
			for indx4, p4 in enumerate(permutations_3):
				permutations_4, keep_string4, all_perms = get_permutations(p4,4, sent, all_perms, type_script, cut_off)
			
				for indx5, p5 in enumerate(permutations_4):
					permutations_5, keep_string5, all_perms = get_permutations(p5,5, sent, all_perms, type_script, cut_off)
					
					for indx6, p6 in enumerate(permutations_5):
						permutations_6, keep_string6, all_perms = get_permutations(p6,6, sent, all_perms, type_script, cut_off)
						
						for indx7, p7 in enumerate(permutations_6):
							permutations_7, keep_string7, all_perms = get_permutations(p7,7, sent, all_perms, type_script, cut_off)
							
							for indx8, p8 in enumerate(permutations_7):
								permutations_8, keep_string8, all_perms = get_permutations(p8,8, sent, all_perms, type_script, cut_off)
								
								for indx9, p9 in enumerate(permutations_8):
									permutations_9, keep_string9, all_perms = get_permutations(p9,9, sent, all_perms, type_script, cut_off)
									
									for indx10, p10 in enumerate(permutations_9):
										permutations_10, keep_string10, all_perms = get_permutations(p10,10, sent, all_perms, type_script, cut_off)
										
										for indx11, p11 in enumerate(permutations_10):
											permutations_11, keep_string11, all_perms = get_permutations(p11,11, sent, all_perms, type_script, cut_off)
											
											for indx12, p12 in enumerate(permutations_11):
												permutations_12, keep_string12, all_perms = get_permutations(p12,12, sent, all_perms, type_script, cut_off)
												add_string = do_string_adjustments(permutations_12, keep_string12)
												keep_string11 += add_string.replace('  ',' ')
										
											keep_string10 += fix_paren(keep_string11)
										
										keep_string9 += fix_paren(keep_string10)
									
									keep_string8 += fix_paren(keep_string9)
									
								keep_string7 += fix_paren(keep_string8)
							
							keep_string6 += fix_paren(keep_string7)				
	
						keep_string5 += fix_paren(keep_string6)
							
					keep_string4 += fix_paren(keep_string5)
				
				keep_string3 += fix_paren(keep_string4)
				
			keep_string2 += fix_paren(keep_string3)
				
		final_string += fix_paren(keep_string2)
			
	final_string = fix_paren(final_string)
	
	return final_string	

									
def process_file_best(amrs, sent_amrs, cut_off):
	'''Permute AMR so that it best matches the word order'''
		
	save_all_amrs = []
	
	assert len(amrs) == len(sent_amrs)
	
	for idx, amr in enumerate(amrs):		
		if amr.count(':') > 1:		## only try to do something if we can actually permutate					
			permutations, keep_string1, _ = get_permutations(amr,1, sent_amrs[idx], [], 'order', cut_off)
			final_string 				  = get_best_perm(permutations, '(' + keep_string1, sent_amrs[idx], '(' + keep_string1, [], 'order', cut_off)			
			save_all_amrs.append(create_final_line(final_string))	## add final string + final parenthesis 
		else:
			save_all_amrs.append(remove_alignment(amr))			## else just add AMR without alignment information
	
	for idx, a in enumerate(amrs):
		amrs[idx] = amrs[idx].replace(' )',')')
		amrs[idx] = remove_alignment(amrs[idx])
	
	changed_amrs = len(amrs) -  len([i for i, j in zip(amrs, save_all_amrs) if i == j])
	
	print 'Changed {0} out of {1} amrs'.format(changed_amrs, len(amrs))
	
	return save_all_amrs, amrs


def preprocess(f_path):
	'''Preprocess the AMR file, deleting variables/wiki-links and tokenizing'''
	
	no_wiki_amrs        = delete_wiki(f_path)
	del_amrs 		    = delete_amr_variables(no_wiki_amrs)
	old_amrs, sent_amrs = single_line_convert(del_amrs)				# old amrs with deleted wiki and variables
	
	return sent_amrs, old_amrs


def create_output(f, old_amrs, new_amrs, sent_amrs):
	'''Print output to the correct files - also keep no-var AMR'''
	
	permuted_amr, no_var_amr, sent_file, double_sent_file, double_amr_file = get_filenames(f_path, args.amr_ext)
		
	write_to_file(old_amrs, no_var_amr)
	write_to_file(new_amrs, permuted_amr)
	write_to_file(sent_amrs, sent_file)
	
	if args.double:
		write_to_file(old_amrs + new_amrs, double_amr_file)
		write_to_file(sent_amrs + sent_amrs, double_sent_file)


def get_filenames(f, amr_ext):
	permuted_amr = f.replace(amr_ext, '.tf.best')
	no_var_amr   = f.replace(amr_ext, '.tf')
	sent_file 	 = f.replace(amr_ext, '.sent')
	double_sent  = f.replace(amr_ext, '.sent.double')
	double_amr   = f.replace(amr_ext ,'.tf.double')
	
	return permuted_amr, no_var_amr, sent_file, double_sent, double_amr
	

if __name__ == '__main__':
	args = create_args_parser()
	
	
	for root, dirs, files in os.walk(args.f):
		for f in files:
			if f.endswith(args.amr_ext):
				print 'Processing {0}'.format(f)
				
				f_path = os.path.join(root,f)
				sent_amrs, old_amrs = preprocess(f_path)
				new_amrs, old_amrs	= process_file_best(old_amrs, sent_amrs, args.cut_off)
				
				create_output(f_path, old_amrs, new_amrs, sent_amrs)	
