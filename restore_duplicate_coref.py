#!/usr/bin/env python
# -*- coding: utf8 -*-

'''Script that adds coreference back in produced AMRs. It does this by simply replacing duplicate nodes by the reference to the variable of the first node.

Input needs to be in one-line format, with variables present.

Sample input:

(e / establish-01 :ARG1 (m / model :mod (i / innovate-01 :ARG1 (i2 / industry) :ARG1 (m2 / model) :ARG1 (i3 / innovate-01))))

Sample output:

(e / establish-01 :ARG1 (m / model :mod (i / innovate-01 :ARG1 (i2 / industry) :ARG1 m :ARG1 i)))'''

import sys
import re
import argparse
from amr_utils import valid_amr, write_to_file, remove_char_outside_quotes


def create_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--input_file", required=True, type=str, help="File that contains AMRs to be processed")
    parser.add_argument("-o", "--output_ext", default='.coref', type=str, help="Output extension of AMRs (default .coref)")
    args = parser.parse_args()
    return args


def process_var_line(line, f):
    '''Function that processes line with a variable in it. Returns the string without
       variables and the dictionary with var-name + var - value'''
    var_list = []
    curr_var_name, curr_var_value, skip_first, current_quotes = False, False, False, False
    var_value, var_name = '', ''

    # Loop over line character by character
    for ch in line:
        # We start adding the variable value (if not between quotes)
        if ch == '/' and not current_quotes:
            curr_var_value = True
            curr_var_name = False
            var_value = ''
            continue
        # We start adding the variable value
        elif ch == '(' and not current_quotes:
            curr_var_name = True
            curr_var_value = False
            # We found a name-value pair, add it now
            if var_value and var_name:
                # Skip first entry, but only do it once. We never want to refer to the full AMR.
                if not var_list and skip_first:
                    skip_first = False
                else:
                    add_var_value = remove_char_outside_quotes(var_value.strip(), ')')
                    var_list.append([var_name.strip(), add_var_value])
            var_name = ''
            continue
        # Keep track of quotes, for tricky instances like :wiki "HIV/AIDS" or :value "2/3"
        elif ch == '"':
            current_quotes = not current_quotes

        # Check if we are adding the current characters to var value/name
        if curr_var_name:
            var_name += ch
        elif curr_var_value:
            var_value += ch
    # Add last one
    var_list.append([var_name.strip(), remove_char_outside_quotes(var_value.strip(), ')')])

    # Check if all output looks valid
    for item in var_list:
        try:
            # Keep in :quant 5 as last one, but not ARG1: or :mod
            if not item[1].split()[-1].isdigit() and len(item[1].split()) > 1:
                item[1] = " ".join(item[1].split()[0:-1])
        except:
            print('Small error, just ignore: {0}'.format(item))  #should not happen often, but strange, unexpected output is always possible
    return var_list


def process_file(f):
    '''Restore duplicate coreference output for a file of AMRs'''
    coref_amrs = []
    # Loop over AMRs (one per line in file)
    for indx, line in enumerate(open(f, 'r')):
        # Get list of variables and concepts present in full AMR
        var_list = process_var_line(line, f)
        new_line = line

        # Loop over this var list to rewrite variable + value to a previous instantiation of this value
        # In other words, if we saw (b / boy) already, rewrite (b2 / boy) to b
        for idx in range(len(var_list)-1):
            for y in range(idx+1, len(var_list)):
                # Match - we see a concept (var-value) we already saw before
                if var_list[idx][1] == var_list[y][1]:
                    replace_item = var_list[y][0] + ' / ' + var_list[y][1]
                    # The part that needs to be replaced should be present
                    if replace_item in line:
                        # Do the actual replacing here, e.g. replace :ARG1 (var / value) by :ARG refvar
                        new_line_replaced = re.sub(r'\({0} / [^\(]*?\)'.format(var_list[y][0]), ' ' + var_list[idx][0], new_line)
                        # Only do replacing if resulting AMR is valid
                        if new_line_replaced != new_line and valid_amr(new_line_replaced):
                            new_line = new_line_replaced
        # Perhaps fix some weird tokenization issues
        new_line = new_line.replace('_ (', '_(').replace(') "', ')"')
        coref_amrs.append(new_line.strip())

    # Sanity check
    assert len(coref_amrs) == indx + 1
    return coref_amrs


if __name__ == '__main__':
    args = create_arg_parser()
    # Do main processing here
    coref_amrs = process_file(args.input_file)
    # Write results to output file
    write_to_file(coref_amrs, args.input_file + args.output_ext)
