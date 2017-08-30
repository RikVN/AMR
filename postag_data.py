import os
import sys
import argparse
import time
from amr_utils import *

'''Script that POS-tags input sentences. Sentences should be each in 1 line.
   Also replaces punctuation POS-tags, since they are unneccessary for AMR parsing.
   
   Relies on the fact that you installed a POS-tagger that can be used. I use the C&C POS-tagger.
   Please change the script appropriately when using a different tagger.'''


def create_arg_parser():

	parser = argparse.ArgumentParser()
	parser.add_argument("-f", required=True, type=str, help="Input sentence file")
	parser.add_argument("-pos_ext", default = '.pos',  required=False, type=str, help="Output extension for POS-tagged file")
	args = parser.parse_args()
	
	return args


def postag_file(in_f, out_f):
	tagger = '/net/gsb/pmb/ext/candc/bin/pos'
	model  = '/net/gsb/pmb/ext/candc/models/boxer/pos/'
	
	os_call = "cat {0} | sed -e 's/|/\//g' | sed 's/^ *//;s/ *$//;s/  */ /g;' | {1} --model {2} --output {3} --maxwords 5000".format(in_f, tagger, model, out_f + '_temp')
	os.system(os_call)
	
	#replace POS-tags for punctuation
	
	repl_call = "cat {0} | sed 's/,|,/,/g' | sed 's/\.|\./\./g' | sed 's/!|\./!/g' | sed 's/;|;/;/g' | sed 's/-|:/-/g' | sed 's/:|:/:/g' > {1}".format(out_f  + '_temp', out_f)
	os.system(repl_call)
	os.system('rm {0}'.format(out_f + '_temp'))	#remove temp file


if __name__ == '__main__':
	args = create_arg_parser()
	postag_file(args.f, args.f + args.pos_ext)
				
