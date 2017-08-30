#!/usr/bin/env python
# -*- coding: utf8 -*-

'''Script that takes one-line AMRs as input and returns one-line AMRs with Wikipedia links added

Sample input for sentence "Prince likes himself":

(l / like :ARG0 (p / person :name "Prince") :ARG1 p)      

Sample output:

(l / like :ARG0 (p / person :name "Prince" :wiki "Prince_(musician)") :ARG1 p)

:wiki "Prince_(musician)" refers to Wikipedia page https://en.wikipedia.org/wiki/Prince_(musician)'''

from time import sleep
import re, os, requests, argparse
from bs4 import BeautifulSoup
from amr_utils import *
import sys
reload(sys)


def create_arg_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument('-f', required = True,  type=str, help='Path to a single file for Wikification - AMRs should be in one line format')
	parser.add_argument('-s', required = True,  type=str, help='Sentence file for Wikification')
	args = parser.parse_args()
	
	return args


def get_wiki_from_spotlight_by_name(spotlight, name):
	'''Given the spotlight output, and a name string, e.g. 'hong kong'
	returns the wikipedia tag assigned by spotlight, if it exists, else '-'.'''
	
	actual_found = 0
	parsed_spotlight = BeautifulSoup(spotlight.text, 'lxml')
	for wiki_tag in parsed_spotlight.find_all('a'):

		if wiki_tag.string.lower() == name.lower():
			actual_found += 1
			return wiki_tag.get('href').split('/')[-1], actual_found
	
	# If nothing found, try to match based on prefixes, e.g. match the name Estonia to the tag for 'Estonian'
	
	for wiki_tag in parsed_spotlight.find_all('a'):
		if wiki_tag.string.lower()[:len(name)] == name.lower():
			actual_found += 1
			return wiki_tag.get('href').split('/')[-1], actual_found
	
	return '-', actual_found


def get_name_from_amr_line(line):
	'''Takes an AMR-line with a :name, returns the full name as a string'''
	name_parts = re.findall(':op[0-9]+ ".*?"', line)
	name_parts = [x[6:-1] for x in name_parts] # Remove garbage around name parts
	return ' '.join(name_parts)


def wikify_file(in_file, in_sents):
	'''Takes .amr-files as input, outputs .amr.wiki-files
	with wikification using DBPedia Spotlight.'''
	
	sentences = [x.strip() for x in open(in_sents,'r')]
	all_found = 0
	unicode_errors = 0
	
	with open(in_file, 'r') as infile:
		with open(in_file + '.wiki', 'w') as outfile:
			foundName = False
			foundWiki = False
			currName = ''  # String to contain the parts of names found
			spotlight = '' # Spotlight results
	
			for idx, line in enumerate(infile):
				sentence = sentences[idx]
						
				# Spotlight raises an error if too many requests are posted at once
				success = False
				
				while not success:
					try:
						#Old servers here
						#spotlight = requests.post("http://spotlight.sztaki.hu:2222/rest/annotate", data = {'text':sentence, 'confidence':0.3})
						#spotlight = requests.post("http://model.dbpedia-spotlight.org:2222/rest/annotate", data = {'text':sentence, 'confidence':0.3})
						
						spotlight = requests.post("http://model.dbpedia-spotlight.org/en/annotate", data = {'text':sentence, 'confidence':0.3})
						spotlight.encoding = 'utf-8'
					except requests.exceptions.ConnectionError:
						print 'sleeping a bit (spotlight overload) - if this keeps happening server is down or changed'
						sleep(0.1)
						continue
					success = True
						
				if sentence:
					name_split = line.split(':name')
					for name_idx in range(1, len(name_split)):	  # skip first in split because name did not occur there yet
						name = get_name_from_amr_line(name_split[name_idx])
						if name != '':
							wiki_tag, actual_found = get_wiki_from_spotlight_by_name(spotlight, name)
							all_found += actual_found
							if wiki_tag != '-': # Only add when we found an actual result
								do_something = 1
								name_split[name_idx-1] += ':wiki "' + wiki_tag + '" '
								
					try:
						wikified_line = ":name".join(name_split).strip().encode('utf-8')
					except:	#unicode error
						unicode_errors += 1
						wikified_line = line.strip()
						
					outfile.write(wikified_line + '\n')
					

if __name__ == '__main__':
	args = create_arg_parser()
	wikify_file(args.f, args.s)
