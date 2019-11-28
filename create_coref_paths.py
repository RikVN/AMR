#!/usr/bin/env python
# -*- coding: utf8 -*-

'''Script that converts the AMRs to a single line, taking care of re-entrancies in a nice way
   It does this by adding the absolute or relative paths. Currently, only absolute paths are implemented.
   Method is described in "Dealing with Co-reference in Neural Semantic Parsing", Van Noord and Bos, 2017

  Sample input:

   # ::snt Bob likes himself.

   (l / like
        :ARG0 (p / person :name "Bob")
        :ARG1 p)

   Sample output *.tf:

    (like :ARG0 (person :name "Bob") :ARG1 ( { :ARG0 |1| } ))'''

import sys
import re
import argparse
import os
from amr_utils import write_to_file, space_brackets_amr, reverse_tokenize, between_quotes, left_space_for_char, add_to_dict
from var_free_amrs import delete_wiki, single_line_convert


def create_arg_parser():
    '''Create argument parser'''
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--input_file", required=True, type=str, help="directory that contains the amrs")
    parser.add_argument('-fol', '--folder', action='store_true', help='Add to do multiple files in a folder - if not, -f is a file')
    parser.add_argument('-a', '--amr_ext', default='.txt', help="extension of AMR files (default .txt, only necessary when doing folder")
    parser.add_argument('-o', '--output_ext', default='.tf', help="extension of output AMR files (default .tf)")
    parser.add_argument('-p', "--path", required=True, choices=['rel', 'abs'], help='Add relative or absolute path (only abs implemented)')
    parser.add_argument('-k', '--keep_wiki', action='store_true', help='Keep Wiki link when processing')
    parser.add_argument('-ps', '--print_stats', action='store_true', help='Print coreference statistics')
    args = parser.parse_args()
    return args


def replace_coreference(one_line_amrs, print_stats):
    '''Function that replaces coreference entities by its relative or absolute path
       Also normalizes the input, references to variables can not be before instantiation'''
    new_amrs = []
    coref_amrs = []
    path_dict = {}

    # Tokenize AMRs
    amrs = [space_brackets_amr(x).split() for x in one_line_amrs]
    # We always skip stuff such as :mode interrogative as possible variables
    no_var_list = ['interrogative', 'expressive', 'imperative']

    # Loop over all AMRs
    for count, spl in enumerate(amrs):
        # Find the path for each variable, save in dict
        var_dict = get_var_dict(spl)
        cur_path = []
        all_paths = []
        new_spl = []
        vars_seen = []
        level, previous_close = 0, False
        # Loop over all tokens in AMR
        # Skip first parenthesis to make things easier, add later
        for idx in range(1, len(spl)):
            # Add all parts, if it is a variable and needs changing we do that later
            new_spl.append(spl[idx])

            # Skip last item, never coreference variable
            if idx == (len(spl) -1):
                continue

            # Check if entity looks like a coreference variable
            var_check, vars_seen = variable_match(spl, idx, no_var_list, vars_seen)

            # Opening parenthesis, means we have to add the previous argument to our path
            if spl[idx] == '(':
                level += 1
                cur_path, all_paths = find_cur_path_addition(cur_path, spl, idx, all_paths)
                previous_close = False
            # Closing, decrease level by 1
            elif spl[idx] == ')':
                level -= 1
                previous_close = True
            # We previously saw a closing parenthesis, means we have finished the last part of our path
            elif previous_close:
                cur_path = cur_path[0:level]
                previous_close = False
            elif var_check:
                previous_close = False
                # Not a relation or value, often re-entrancy, check whether it exists
                if not (spl[idx].startswith(':') or spl[idx].startswith('"')):
                    if spl[idx] in var_dict:
                        # Found variable, check paths here
                        path_dict, all_paths, new_spl, _ = add_path_to_amr(spl, idx, var_dict, cur_path, count, path_dict, all_paths, new_spl, coref_amrs)
            # We saw a non-interesting entity, just continue
            else:
                previous_close = False

        # Reverse tokenization process of AMRs regarding parentheses
        new_line = '(' + " ".join(new_spl)
        new_line = reverse_tokenize(new_line)
        new_amrs.append(new_line)

    # Sanity check
    assert len(amrs) == len(new_amrs)
    # Print some stats
    if print_stats:
        print_coref_stats(coref_amrs, path_dict)
    return new_amrs


def get_var_dict(spl):
    '''Function that returns a dictionary with all variables and their absolute path for an AMR'''

    cur_path = []
    level = 0
    all_paths = []
    var_dict = dict()
    previous_close = False

    # Skip first parenthesis
    for idx in range(1, len(spl)):
        if spl[idx] == '(':
            level += 1
            cur_path, all_paths = find_cur_path_addition(cur_path, spl, idx, all_paths)
            previous_close = False
        elif spl[idx] == ')':
            level -= 1
            previous_close = True
        elif spl[idx] == '/':
            # Var found
            var_name = spl[idx-1]
            var_value = spl[idx+1]
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
    elif spl[idx-1] != '/' and any(char.isalpha() for char in spl[idx]) and spl[idx] not in no_var_list and not between_quotes(spl[idx]) and not spl[idx].startswith(':'):
        return True, vars_seen
    else:
        return False, vars_seen


def find_cur_path_addition(cur_path, spl, idx, all_paths):
    '''Function that finds what we have to add to our current path'''
    counter = 1
    found_before = False
    for c in range(15, 1, -1):
        # If there are multiple occurences, add the next one (2,3,4,5 etc)
        to_add = "".join(cur_path) + spl[idx-1] + '|{0}|'.format(c)
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
        print('Something is wrong')

    return cur_path, all_paths


def remove_variables(amrs):
    '''Replace variables in AMR'''
    new_amrs = []
    for a in amrs:
        add_enter = re.sub(r'(:[a-zA-Z0-9-]+)(\|\d\|)', r'\1 \2', a)
        p = re.findall(r'\(([a-zA-Z0-9-_\. ]+/)', add_enter)
        for x in p:
            if '"' not in x:
                add_enter = add_enter.replace(x, '')
        final_string = left_space_for_char(add_enter, '(')
        new_amrs.append(reverse_tokenize(final_string))
    return new_amrs


def add_path_to_amr(spl, idx, var_dict, cur_path, count, path_dict, all_paths, new_spl, coref_amrs):
    '''Function that finds the path that needs to be added and adds it'''
    # We skipped this part of the path because it doesn't start with a parenthesis, still add it here
    if spl[idx-1].startswith(':'):
        cur_path, all_paths = find_cur_path_addition(cur_path, spl, idx, all_paths)

    if args.path == 'rel':
        raise NotImplementedError("Relative paths are not implemented yet")
    else:
        # Add absolute path here
        new_spl[-1] = '{ ' + var_dict[spl[idx]][1]  + ' }'
        add_path = var_dict[spl[idx]][1]

        # Check if we already added this AMR
        if not coref_amrs or coref_amrs[-1] != count:
            coref_amrs.append(count)
        path_dict = add_to_dict(path_dict, add_path, 1)
    return path_dict, all_paths, new_spl, add_path


def print_coref_stats(coref_amrs, path_dict):
    '''Print interesting statistics about coref parsing'''
    print('Length of AMRs with coref: {0}'.format(len(coref_amrs)))
    total, once, max_len = 0, 0, 0

    # Check in the path dictionary
    for key in path_dict:
        total += 1
        if path_dict[key] == 1:
            once += 1

        if len(key.split()) > max_len:
            max_len = len(key.split())
            long_path = key

    # Print results for longest path only if we have it
    if max_len > 0:
        print('Longest path: {0}\nOf length: {1}\n'.format(long_path, max_len))
    print('{0} out of {1} are unique'.format(once, total))


def create_coref_paths(input_file, output_ext, keep_wiki, print_stats):
    '''Main function to create the coreference paths'''
    # Delete wiki links only if we want to
    amr_file_no_wiki = delete_wiki(input_file) if not keep_wiki else [x.rstrip() for x in open(input_file, 'r')]
    # Put the AMRs on a single line
    single_amrs, _ = single_line_convert(amr_file_no_wiki, '')
    # Replace coreference with paths of our choice
    repl_amrs = replace_coreference(single_amrs, print_stats)
    final_amrs = remove_variables(repl_amrs)
    # Write final AMRs to a file
    write_to_file(final_amrs, input_file + output_ext)


if __name__ == "__main__":
    args = create_arg_parser()

    # Either do a single file or loop over files in folder
    if not args.folder:
        create_coref_paths(args.input_file, args.output_ext, args.keep_wiki, args.print_stats)
    else:
        for root, dirs, files in os.walk(args.input_file):
            for f in files:
                if f.endswith(args.amr_ext):
                    create_coref_paths(os.path.join(root, f), args.output_ext, args.keep_wiki, args.print_stats)

