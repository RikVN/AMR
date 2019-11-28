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

(want :ARG1 (*1* person :name "Jack") :ARG3 (buy :ARG1 *1* :ARG2 (ice-cream)))'''


import sys
import argparse
import os
from amr_utils import write_to_file, space_brackets_amr, reverse_tokenize, variable_match
from var_free_amrs import delete_wiki, single_line_convert


def create_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--input_file', required=True, type=str, help="File with AMRs")
    parser.add_argument('-fol', '--folder', action='store_true', help='Add to do multiple files in a folder - if not, args.f is a file')
    parser.add_argument('-a', '--amr_ext', default='.txt', help="Extension of AMR files (default .txt, only necessary when doing folder")
    parser.add_argument('-o', '--output_ext', default='.tf', help="Extension of output AMR files (default .tf)")
    parser.add_argument('-k', '--keep_wiki', action='store_true', help='Keep Wiki link when processing')
    args = parser.parse_args()
    return args


def coreference_index(one_line_amrs):
    '''Function that replaces coreference entities by its relative or absolute path'''
    new_amrs = []
    # Tokenize AMRs
    amrs = [space_brackets_amr(x).split() for x in one_line_amrs]
    # We always skip stuff such as :mode interrogative as possible variables
    no_var_list = ['interrogative', 'expressive', 'imperative']

    # Loop over AMRs
    for spl in amrs:
        all_vars = []
        # Loop over all tokens in AMR and save variables
        for idx in range(0, len(spl)):
            # Check if entity looks like a coreference variable
            if variable_match(spl, idx, no_var_list):
                all_vars.append(spl[idx])

        vars_seen, new_spl = [], []
        # Loop over tokens again and check if we want to rewrite variables
        for idx in range(0, len(spl)):
            if variable_match(spl, idx, no_var_list):
                # If entity occurs at least twice, make mention of it
                if all_vars.count(spl[idx]) > 1:
                    if spl[idx] in vars_seen:
                        # Already saw the variable, add index path
                        new_spl.append('*{0}*'.format(vars_seen.index(spl[idx])))
                    else:
                        # Did not see variable before, add new one
                        new_spl.append('*{0}*'.format(len(vars_seen)))
                        vars_seen.append(spl[idx])
            # Skip items that were part of a variable (not there anymore)
            elif spl[idx] != '/':
                new_spl.append(spl[idx])

        # Reverse tokenize and save AMRs
        new_line = " ".join(new_spl)
        new_line = reverse_tokenize(new_line)
        new_amrs.append(new_line)

    # Sanity check
    assert len(amrs) == len(new_amrs)
    return new_amrs


def create_coref_indexing(input_file, output_ext, keep_wiki):
    '''Go from full AMR to one-line AMR without wiki with coreference indexed'''
    # Remove all Wiki instances
    amr_file_no_wiki = delete_wiki(input_file) if not keep_wiki else [x.rstrip() for x in open(input_file, 'r')]
    # Put everything on a single line, sent_file is empty
    single_amrs, _ = single_line_convert(amr_file_no_wiki, '')
    # Add the coference index we want
    repl_amrs = coreference_index(single_amrs)
    # Write output to file
    write_to_file(repl_amrs, input_file + output_ext)


if __name__ == "__main__":
    args = create_arg_parser()

    # Either do single file or loop over folder to select files
    if not args.folder:
        create_coref_indexing(args.input_file, args.output_ext, args.keep_wiki)
    else:
        for root, dirs, files in os.walk(args.input_file):
            for f in files:
                if f.endswith(args.amr_ext):
                    create_coref_indexing(os.path.join(root, f), args.output_ext, args.keep_wiki)



