#!/usr/bin/env python3


'''Script that restores AMR variables. Most of the code is from https://github.com/didzis/tensorflowAMR/tree/master/SemEval2016

Possible to restore AMRs that used the Indexing or Paths method, described in "Dealing with Co-reference in Neural Semantic Parsing", Van Noord and Bos, 2017

Sample input:
   
( l o o k - 0 1 + :mode + i m p e r a t i v e + :ARG0 + ( y o u ) )
   
Sample output:

(vvlook-01 / look-01 :mode imperative :ARG0 (vvyou / you))'''


import sys, re, os, json, random, argparse
from amr_utils import *
from trans import translate, restore
from best_amr_permutation import filter_colons, get_keep_string, get_add_string
from var_free_amrs import process_var_line


### General functions ###


unbracket = re.compile(r'\(\s*([^():\s"]*)\s*\)')
dangling_edges = re.compile(r':[\w\-]+\s*(?=[:)])')
missing_edges = re.compile(r'(\/\s*[\w\-]+)\s+\(')
missing_variable = re.compile(r'(?<=\()\s*([\w\-]+)\s+(?=:)')
missing_quotes = re.compile(r'("\w+)(?=\s\))')
misplaced_colon = re.compile(r':(?=\))')
missing_concept_and_variable = re.compile(r'(?<=\()\s*(?=:\w+)')
dangling_quotes = re.compile(r'(?<=\s)(\w+)"(?=\s|\)|:)')


def create_arg_parser():

	parser = argparse.ArgumentParser()
	parser.add_argument("-f", required = True, type=str, help="File with AMRs (one line)")
	parser.add_argument("-o", required = True, type=str, help="Output file")
	parser.add_argument("-index", action = 'store_true', help="File has indexed paths")
	parser.add_argument("-abs", action = 'store_true', help="File has absolute paths")
	args = parser.parse_args()
	
	return args


def preprocess(line, absolute):
	line = line.replace(' ','').replace('+',' ').replace(':polarity-',':polarity100')	#otherwise polarity nodes get removed, this gets restored in later step
	if absolute:
		line = preprocess_abs(line)	#absolute paths need a different preprocessing step
	return line	


def initial_check(index, absolute):
	'''Do initial checks and prints, load dicts as well'''
	
	if index and absolute:
		print "Don't do both paths and indexing, quitting..."
		sys.exit(0)
	elif index:
		replace_types = ['Normal case', 'Replace by variable that is not referred to','Replace by most frequent index', 'Replace by most frequent concept','No concepts found - do person']
		print '\nRestoring with Index method'
	elif absolute:
		replace_types = ['Path lead to variable','Path did not lead to variable']
		print '\nRestoring with Paths method...\n'
	else:
		replace_types = [] 	#not needed
		print '\nRestoring with normal method'	
	
	ref_dict = load_dict('restoreAMR/ref_dict')	#dictionary with frequency information
	index_dict = dict.fromkeys(replace_types, 0)
	
	return ref_dict, index_dict, replace_types


## General restore functions (mostly from https://github.com/didzis/tensorflowAMR/tree/master/SemEval2016) ###


def remove_dangling_edges(line):
	if line[-1] != ')':                                 #remove unfinished edges (can happen with char-level output)
		line = ")".join(line.split(')')[:-1]) + ')'
	
	return line
	
	
def replace_var(m):
	global c
	global cc
	global ggg

	if ['name','date'].count(m.group(1)) == 1:
		c += 1
		return '(v' + str(ggg) + str(c) + ' / ' + m.group(1) + m.group(2)
	if cc.count(m.group(1)) == 0:
		cc.append(m.group(1))
		return '(vv' + str(ggg) + m.group(1) + ' / ' + m.group(1) + m.group(2)
	if m.group(2) == ' )':
	   return ' vv' + str(ggg) + m.group(1)
	c += 1
	return '(vvvv' + str(ggg) + str(c) + ' / ' + m.group(1) + m.group(2)
	

def replace_var2(m):
	if m.group(2) == "-":
		return "%s %s" % (m.group(1), m.group(2))
	if m.group(2) == "interrogative":
		return "%s %s" % (m.group(1), m.group(2))
	if m.group(2) == "expressive":
		return "%s %s" % (m.group(1), m.group(2))
	if m.group(2) == "imperative":
		return "%s %s" % (m.group(1), m.group(2))
	return "%s \"%s\"" % (m.group(1),  m.group(2))


def add_quotes(m):
	value = m.group(2).strip()
	if value == '-':
		return '%s %s ' % (m.group(1), value)
	return '%s "%s" ' % (m.group(1), value)

def convert(line):
	line = line.rstrip().lstrip(' \xef\xbb\xbf\ufeff')
	line = line.rstrip().lstrip('> ')
	
	global cc
	global c
	global ggg
	c = 0
	cc=[]
	old_line = line
	
	while True:
		line = re.sub(r'(\( ?name [^()]*:op\d+|:wiki) ([^\-_():"][^():"]*)(?=[:\)])', add_quotes, line, re.I)
		if old_line == line:
			break
		old_line = line

	line = re.sub(r'\(\s*([\w\-\d]+)(\W.|\))', replace_var, line)

	line = re.sub(r'"(_[^"]+)"', lambda m: restore(m.group(1)), line)

	open_count = 0
	close_count = 0
	
	for i,c in enumerate(line):
		if c == '(':
			open_count += 1
		elif c == ')':
			close_count += 1
		if open_count == close_count and open_count > 0:
			line = line[:i].strip()
			break

	old_line = line
	
	while True:
		open_count = len(re.findall(r'\(', line))
		close_count = len(re.findall(r'\)', line))
		if open_count > close_count:
			line += ')' * (open_count-close_count)
		elif close_count > open_count:
			before = line
			for i in range(close_count-open_count):
				line = line.rstrip(')')
				line = line.rstrip(' ')

		if old_line == line:
			break
		old_line = line

	old_line = line
	
	while True:
		line = re.sub(r'(:\w+) ([^\W\d\-][\w\-]*)(?=\W)', replace_var2, line, re.I)
		if old_line == line:
			break
		old_line = line
	
	line = unbracket.sub(r'\1', line, re.U)

	line = dangling_edges.sub('', line, re.U)

	line = missing_edges.sub(r'\1 :ARG2 (', line, re.U)

	line = missing_variable.sub(r'vvvx / \1 ', line, re.U)

	line = missing_quotes.sub(r'\1"', line, re.U)

	line = misplaced_colon.sub(r'', line, re.U)

	line = missing_concept_and_variable.sub(r'd / dummy ', line, re.U)

	line = dangling_quotes.sub(r'\1', line, re.U)

	return line


def add_space_when_digit(line):
	'''Add a space when see a digit, except for arguments of id_list'''
	id_list = ['ARG','op','snt','-']
	
	spl = line.split(':')
	for idx in range(1, len(spl)):
		if spl[idx].strip().replace(')',''):
			if (spl[idx].strip().replace(')','')[-1].isdigit() and (not any(x in spl[idx] for x in id_list))):        ## if there is a digit after quant or value, put a space so we don't error, e.g. :value3 becomes :value 3, but not for op, snt and ARG
				new_string = ''
				added_space = False
				for ch in spl[idx]:
					if ch.isdigit():
						if not added_space:
							new_string += ' ' + ch
							added_space = True
						else:
							new_string += ch    
					else:
						new_string += ch
				spl[idx] = new_string
			
			elif (spl[idx].replace(')','').replace('ARG','').isdigit()):                #change ARG2444 to ARG2 444
				spl[idx] = re.sub(r'(ARG\d)([\d]+)',r'\1 \2',spl[idx])
	return ':'.join(spl)      
		

def do_extra_steps(line):
	line = line.replace(':',' :')               # colon has no spaces
	line = line.replace('(',' (')
	for x in range(0,25):                       # change :op0"value" to :op0 "value" as to avoid errors
		line = line.replace(':op' + str(x) + '"', ':op' + str(x) + ' "')
	
	line = line.replace(':value"',':value "')
	line = line.replace(':time"',':time "')
	line = line.replace(':li"',':li "')
	line = line.replace(':mod"',':mod "')
	line = line.replace(':timezone"',':timezone "')
	line = line.replace(':era"',':era "')
	
	quotes = 0
	prev_char = 'a'
	new_line = ''
	
	for ch in line:
		if ch == '"':
			quotes += 1
			if quotes % 2 != 0 and new_line[-1] != ' ':
				new_line += ' "'                            #add space for quote
			else:
				new_line += ch  
		else:
			new_line += ch
	
	new_line = re.sub('(op\d)(\d\d+)',r'\1 \2',new_line)     #fix problem with op and numbers, e.g. change op123.5 to op1 23.5           
	new_line = re.sub(r'(op\d)(\d+)\.(\d+)',r'\1 \2.\3',new_line)
	new_line = re.sub(r'(mod\d)(\d+)\.(\d+)',r'\1 \2.\3',new_line)
	new_line = re.sub(r'(ARG\d)(\d+)\.(\d+)',r'\1 \2.\3',new_line)
	new_line = new_line.replace(':polarity 100',':polarity -')
	return new_line


### Function to process AMRs that used the Indexing method to solve coreference ###				


def restore_coref_indexing(line, ref_dict):
	'''Restore coreference items, e.g. *3* and *2* with actual word'''
	
	pattern 	= re.compile('^\*[\d]+\*$')
	tok_line 	= line.replace(')',' ) ').replace('(',' ( ').split()	# "tokenize" line
	seen_coref 	= {}
	new_tok 	= []
	
	#First find all instantiated indexes
	
	for idx, item in enumerate(tok_line):
		if pattern.match(item):
			if idx < len(tok_line) -1 and tok_line[idx+1][0].isalpha():			#check if next is a word
				seen_coref[item] = tok_line[idx+1]		#always add if it's a word
	
	for idx, item in enumerate(tok_line):
		if pattern.match(item):	
			if idx == len(tok_line) -1:				#can't look ahead to idx + 1 here
				referent = get_most_frequent_word(tok_line, ref_dict)
				new_tok.append('(coref-{0})'.format(referent))
			
			elif tok_line[idx+1][0].isalpha():		#instantiated case, just removing index is enough
				pass
			
			else:									#replace coref instance	
				if item in seen_coref:				#normal case, reference to instantiated index
					referent = seen_coref[item]
					index_dict[replace_types[0]] += 1
				
				#Problem: we have an index but it was never instantiated
				else:	
					
					if len(seen_coref) > 0:			#current solution, add most frequent other referent (most rather have one that was never instantiated), if they are all not in train set add one at random
						referent = get_most_frequent_referent(seen_coref, ref_dict, tok_line)
					else:							#if there are no other referents just add the most frequent one in general based on all words in sentence
						referent = get_most_frequent_word(tok_line, ref_dict)	#get word that is most frequently referred to
						
				new_tok.append('(coref-{0})'.format(referent))	## bit hacky/ugly, but we have no variables here, we need to recognize that we need to replace this word in a later stage without messing up the restoring variables process		
																## we also add unneccesary brackets to not mess up the variable restoring process, we need to remove them in a later stage as well	
		else:
			new_tok.append(item)
	
	new_line = " ".join(new_tok)
	
	while ' )' in new_line or '( ' in new_line:								#reverse the tokenization process
		new_line = new_line.replace(' )',')').replace('( ','(')
			
	return new_line


def get_most_frequent_word(tok_line, ref_dict):
	'''Function that returns the concept in the AMR (tok_line) that is most frequently a referent in the training set (ref_dict)'''
	
	most_freq, score = '', -1
	words = []
	
	for item in tok_line:
		if item[0].isalpha():
			words.append(item)
			if item in ref_dict:
				if ref_dict[item] > score:
					score = ref_dict[item]
					most_freq = item
	
	if score > -1:			
		index_dict[replace_types[3]] += 1
		return most_freq		#return word that most often has a referent in training set
	elif words:		
		index_dict[replace_types[3]] += 1
		rand_return = random.choice(words[0:-1]) if len(words) > 1 else random.choice(words)
		return rand_return		#no known words from our training set, return random one, last one might be cut-off though so ignore that one
	else:
		index_dict[replace_types[4]] += 1
		return 'person'	


def get_most_frequent_referent(seen_coref, ref_dict, tok_line):
	'''Takes care of indexes that were never instantiated'''
	
	#first check if we have instantiated variables that were never referred to
	
	line = " ".join(tok_line) #put line back
	most_freq = ''
	score = -1
	
	for item in seen_coref:
		if line.count(item) == 1:	#index only occurs once - never used as reference
			if seen_coref[item] in ref_dict:				#if this word in general dict
				if ref_dict[seen_coref[item]] > score:		#check if it is the most frequent
					score = ref_dict[seen_coref[item]]
					most_freq = seen_coref[item]
			else:
				most_freq = seen_coref[item]
				score = 0		
	
	
	if score > -1:	#if we found one
		index_dict[replace_types[1]] += 1
		return most_freq
	
	#else find the most frequent in general
		
	else:
		most_freq = ''
		score = -1
		
		for item in seen_coref:					
			if seen_coref[item] in ref_dict:				#if this word in general dict
				if ref_dict[seen_coref[item]] > score:		#check if it is the most frequent
					score = ref_dict[seen_coref[item]]
					most_freq = seen_coref[item]
		
		if score > -1:
			index_dict[replace_types[2]] += 1
			return most_freq							#return most frequent referent we saw
		else:	
			index_dict[replace_types[2]] += 1
			rand_key = random.choice(seen_coref.keys())		#if no referents with score, return a random one
			return seen_coref[rand_key]


def add_coref(line):
	'''Do the replacement; line includes variables, but we still need to replace 'COREF-person' with 'p', for example'''
	
	var_dict = {}			#first get the variables
	tok_line = tokenize_line(line).split()	

	for idx, item in enumerate(tok_line):
		if item == '/':			#variable in previous tok and value in tok afterwards
			if 'coref-' not in tok_line[idx+1]:
				var_dict[tok_line[idx+1]] = tok_line[idx-1]	
	
	new_tok = []
	ignore_next = False
	
	for idx, item in enumerate(tok_line):		#add coref back
		if item.startswith('coref-'):
			ignore_next = False
			it = item.replace('coref-','')
			if it in var_dict:
				new_tok.append(var_dict[it])
				new_tok[-2], new_tok[-3], new_tok[-4] = '','','' #remove previous 3 items, " ( var / " and next item " ) "
				ignore_next = True
			else:
				new_tok.append('person')
				new_tok[-2], new_tok[-3], new_tok[-4] = '','',''
				ignore_next = True	
		elif not ignore_next:
			new_tok.append(item)
			ignore_next = False	
		else:
			ignore_next = False
	
	new_line = " ".join(new_tok)
					
	return reverse_tokenize(new_line)
				
	
### Function to process AMRs that used the Absolute Paths method to solve coreference ###	
	
	
def preprocess_abs(line):
	'''Put in such a format that restoring still works'''
	
	new_line = " ".join(line.replace('}',' } ').replace('{',' { ').split())
	
	if '{' in new_line:
		line_parts = []
		coref_parts = []
		coref = False
		
		for item in new_line.split():				
			if item == '{':
				line_parts.append('(')	#add brackets
				coref = True
			elif item == '}':
				add_part = 'COREF*' + "*".join(coref_parts).replace(':','COLON')
				line_parts.append(add_part)
				line_parts.append(')')
				coref = False
				coref_parts = []
			elif coref:
				coref_parts.append(item)
			else:
				line_parts.append(item)
		return " ".join(line_parts)
	else:
		return line


def replace_absolute_paths(line, ref_dict):
	'''Replace absolute paths by the correct variable referent'''
	
	spl_line = tokenize_line(line).split()
	new_line = line
	
	for idx, item in enumerate(spl_line):
		if 'COREF*' in item:
			repl = find_replacement(line, item, ref_dict)					#find actual replacement here
			if repl:
				to_be_replaced = " ".join(spl_line[idx-3:idx+2])	#replace this part with the reference
			else:
				to_be_replaced = " ".join(spl_line[idx-4:idx+2])	#remove reference, so also include the argument
			
			new_line = new_line.replace(to_be_replaced, repl)		#do actual replacement here
	
	return reverse_tokenize(new_line)
	

def find_replacement(line, item, ref_dict):
	'''Find variable replacement for the path described in the output'''
	
	path = item.replace('COREF','').replace('COLON',':').replace('*',' ').strip()	#temp changes are put back here
	args = [x for idx, x in enumerate(path.split()) if idx % 2 == 0]
	num =  [x for idx, x in enumerate(path.split()) if idx % 2 != 0]
	nums = [int(x.replace('|','').strip()) for x in num]
	
	concept_dict = get_concepts(line)
	tok_line = tokenize_line(line)
	new_parts = filter_colons(tok_line)					#remove non-arguments that have a colon such as timestamps and websites
	_, search_part = get_keep_string(new_parts, 0)		#get part we have to search	
	
	path_found, search_part = possible_path(args, nums, search_part)	#check if we found a correct path		
	
	if path_found:	#if we found correct path, return it
		index_dict[replace_types[0]] += 1
		return get_reference(search_part)
	else:
		index_dict[replace_types[1]] += 1
		return most_frequent_var(concept_dict, ref_dict)	#else, return the variable the is most frequently a referent in the training set


def get_concepts(line):
	'''Function that returns AMR concepts while restoring for the paths method'''
	
	line = " ".join(line.split())
	_, var_dict = process_var_line(line, {})
	
	for key in var_dict:
		spl = var_dict[key].split()
		if spl[-1].startswith(':'):
			var_dict[key] = " ".join(spl[0:-1])	#solve problems with everything being in one line, e.g. change concept :ARG1 to just concept
			
	return var_dict


def possible_path(args, nums, search_part):
	'''Function that returns whether it is possible to follow the path to a referent'''
	path_found = True
	
	for idx in range(0, len(args)):
		_, permutations = get_add_string(search_part)	
		search_part  = matching_perm(permutations, args[idx], nums[idx])	#check if the output path matches with a path in the AMR
		
		if not search_part:	 #did not find a correct path
			path_found = False
			break
	
	return path_found, search_part		
	
		
def matching_perm(permutations, rel, count):
	'''Check if the current path value matches a possible path in the AMR'''
	
	num_matches, matching_perm = 0, ''
	
	for p in permutations:
		rel_p = p.split()[0]
		if rel_p == rel:
			num_matches += 1
			if num_matches == count:
				matching_perm = p
	return matching_perm


def get_reference(search_part):
	'''Get the correct reference'''
	
	spl_line = search_part.split()
	for idx in range(len(spl_line)):
		if spl_line[idx] == '/':
			ref_var = spl_line[idx-1]
			break
			
	return ref_var


def most_frequent_var(concept_dict, ref_dict):
	'''Get the variable in AMR that is most frequent in training set, based on dictionary of concepts'''
	
	most_freq, score = '', -1
	
	for item in concept_dict:
		if concept_dict[item] in ref_dict:
			if ref_dict[concept_dict[item]] > score:
				score = ref_dict[concept_dict[item]]
				most_freq = item
	
	if score == -1:
		return random.choice(concept_dict.keys())	#no best score found, just return random		
	else:
		return most_freq	


if __name__ == '__main__':
	args = create_arg_parser()
	ref_dict, index_dict, replace_types = initial_check(args.index, args.abs)
	restored_lines = []
	
	global ggg
	ggg = 0
		
	for idx, line in enumerate(open(args.f, 'r')):
		ggg += 1
		
		line = preprocess(line, args.abs)	#abs has separate preprocessing step as well
		
		if args.index:
			line = 	restore_coref_indexing(line, ref_dict)			#fix coref for indexing
		
		#normal restoring steps
		
		line = remove_dangling_edges(line)
		line = add_space_when_digit(line)
		line = convert(line)			#convert line
		line = do_extra_steps(line)		#do some extra steps to fix problems
		
		#do extra steps for certain coreference types
		
		if args.index:
			line = add_coref(line)		#replace the 'coref-' nodes with the reference
		elif args.abs:
			line = replace_absolute_paths(line, ref_dict)	#replace paths here
			
		restored_lines.append(" ".join(line.strip().split()))
	
	#print detailed results for the coreference methods
	
	if args.index or args.abs:
		print 'Results for types of replacements:\n'
		
		for key in replace_types:
			print '{0}: {1}'.format(key, index_dict[key])

	write_to_file(restored_lines, args.o)
