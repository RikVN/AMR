#!/usr/bin/env python
# -*- coding: utf8 -*-

'''Script that removes variables from AMR by duplicating the information, possibly deletes wiki-links
   Presupposes that files have a certain extension (default .txt)

   Sample input:

   # ::snt Bob likes himself.

   (l / like
        :ARG0 (p / person :name "Bob")
        :ARG1 p)

    Output *.tf:

    (like :ARG0 (person :name "Bob") :ARG1 (person :name "Bob"))'''

import sys
import re
import argparse
import os
from amr_utils import write_to_file, remove_char_outside_quotes


def create_args_parser():
    '''Creating arg parser'''
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--input_file", required=True, type=str, help="AMR file or folder")
    parser.add_argument('-fol', "--folder", action='store_true', help='Add to do multiple files in a folder - if not, args.f is a file')
    parser.add_argument('-a', "--amr_ext", default='.txt', type=str, help="Input files must have this extension (default .txt, only necesary when using -fol)")
    parser.add_argument('-o', '--output_ext', default='.tf', help="extension of output AMR files (default .tf)")
    parser.add_argument('-k', '--keep_wiki', action='store_true', help='Keep Wiki link when processing')
    args = parser.parse_args()
    return args


def single_line_convert(lines, sent_file):
    '''Convert AMRs to a single line, ignoring lines that start with "# ::"
      If a sentence file is specified we also try to get the sentences'''
    all_amrs, cur_amr, sents = [], [], []
    for line in lines:
        if not line.strip() and cur_amr:
            cur_amr_line = " ".join(cur_amr)
            all_amrs.append(cur_amr_line.strip())
            cur_amr = []
        elif line.startswith('# ::snt') or line.startswith('# ::tok'):
            # Save sentences as well (don't always need them)
            sent = re.sub('(^# ::(tok|snt))', '', line).strip() #remove # ::snt or # ::tok
            sents.append(sent)
        elif not line.startswith('#'):
            cur_amr.append(line.strip())
    # File did not end with newline, so add AMR here
    if cur_amr:
        all_amrs.append(" ".join(cur_amr).strip())

    # If we didn't find sentences, but we did have a sentence file, read the sentences from there (if possible)
    if not sents and sent_file:
        if os.path.isfile(sent_file):
            sents = [x.strip() for x in open(sent_file, 'r')]
            # Sanity check
            assert len(all_amrs) == len(sents), "{0} vs {1}".format(len(all_amrs), len(sents))
    return all_amrs, sents


def delete_wiki(input_file):
    '''Delete wiki links from AMRs'''
    no_wiki = []
    for line in open(input_file, 'r'):
        n_line = re.sub(r':wiki "(.*?)"', '', line, 1)
        n_line = re.sub(':wiki -', '', n_line)
        # Merge double whitespace but keep leading whitespace
        no_wiki.append((len(n_line) - len(n_line.lstrip())) * ' ' + ' '.join(n_line.split()))
    return no_wiki


def process_var_line(line, var_dict):
    '''Function that processes line with a variable in it. Returns the string without
       variables and the dictionary with var-name + var - value
       Only works if AMR is shown as multiple lines and input correctly!'''
    curr_var_name = False
    curr_var_value = False
    var_value = ''
    var_name = ''
    current_quotes = False
    for ch in line:
        # We start adding the variable value
        if ch == '/' and not current_quotes:
            curr_var_value = True
            curr_var_name = False
            var_value = ''
            continue
        # We start adding the variable name
        elif ch == '(' and not current_quotes:
            curr_var_name = True
            curr_var_value = False
            # We already found a name-value pair, add it now
            if var_value and var_name:
                # Remove closing brackets that were not in between quotes
                add_value = remove_char_outside_quotes(var_value.strip(), ')')
                # Now we have to check: if this previous item starts with ':', we remove it,
                # because that means it started a new part ( :name (n / name ..)
                if add_value.split()[-1].startswith(':'):
                    add_value = " ".join(add_value.split()[:-1])
                var_dict[var_name.strip()] = add_value
            var_name = ''
            continue
        # Check if we are currently within quotes
        elif ch == '"':
            current_quotes = not current_quotes

        # Add to variable name/value
        if curr_var_name:
            var_name += ch
        if curr_var_value:
            var_value += ch

    # Remove brackets that were not within quotes for final var value
    final_var = remove_char_outside_quotes(var_value, ')')
    # Save information to dictionary
    var_dict[var_name.strip()] = final_var
    # Remove variable information from the AMR line
    deleted_var_string = re.sub(r'\([a-zA-Z-_0-9]+[\d]? /', '(', line).replace('( ', '(')
    return deleted_var_string, var_dict


def delete_amr_variables(amrs):
    '''Function that deletes variables from AMRs'''
    full_var_dict = {}
    del_amr = []

    # First get the var dict
    for line in amrs:
        _, full_var_dict = process_var_line(line, full_var_dict)

    # Loop over AMRs to rewrite
    for line in amrs:
        if line.strip() and line[0] != '#':
            if '/' in line:
                # Found variable here
                # Get the deleted variable string and save
                deleted_var_string, _ = process_var_line(line, full_var_dict)
                del_amr.append(deleted_var_string)
            else:
                # Probable reference to variable here!
                split_line = line.split()
                ref_var = split_line[1].replace(')', '')

                # Check if the variable occurs in our dictionary
                if ref_var in full_var_dict:
                    # Get value to replace the variable name with
                    ref_value = full_var_dict[ref_var]
                    # Do the replacing and add brackets for alignment
                    split_line[1] = split_line[1].replace(ref_var, '(' + ref_value.strip() + ')')
                    n_line = (len(line) - len(line.lstrip())) * ' ' + " ".join(split_line)
                    del_amr.append(n_line)
                else:
                    # No reference found, add line without editing (usually there are numbers in this line)
                    del_amr.append(line)
        else:
            # Line with other info, just add
            del_amr.append(line)
    return del_amr


def var_free_amrs(input_file, out_ext, keep_wiki):
    '''Create variable-free AMRs and sentence files'''
    # Delete wiki link if wanted
    amr_no_wiki = delete_wiki(input_file) if not keep_wiki else [x.rstrip() for x in open(input_file, 'r')]
    # Remove all variables by duplicating coreference nodes
    del_amrs = delete_amr_variables(amr_no_wiki)
    # Put AMR on single line and write output
    single_amrs, _ = single_line_convert(del_amrs, '')
    write_to_file(single_amrs, input_file + out_ext)


if __name__ == "__main__":
    args = create_args_parser()

    # Do input file or find files in folder
    if not args.folder:
        var_free_amrs(args.input_file, args.output_ext, args.keep_wiki)
    else:
        for root, dirs, files in os.walk(args.input_file):
            for f in files:
                if f.endswith(args.amr_ext):
                    var_free_amrs(os.path.join(root, f), args.output_ext, args.keep_wiki)

