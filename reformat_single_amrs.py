#!/usr/bin/env python
# -*- coding: utf8 -*-

'''Script that reformats AMRs back to their original format with tabs and enters
   Possibly also checks if the AMRs are valid (errors if they're not)'''

import sys
import argparse
from amr_utils import valid_amr, write_to_file, tokenize_line, reverse_tokenize


def create_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--input_file", required=True, type=str, help="File with the to be formatted AMRs")
    parser.add_argument("-e", "--extension", default='.txt', type=str, help="New extension of formatted AMRs")
    parser.add_argument("-v", "--valid", action='store_true', help="Error when encountering an invalid AMR")
    args = parser.parse_args()
    return args


def variable_match(token):
    '''Function that matches entities that are variables occurring for the second time'''
    if len(token) == 1:
        if not token.isalpha():
            return False
    return any(char.isalpha() for char in token) and any(char.isdigit() for char in token) and not token.startswith(':') and len([x for x in token if x.isalpha() or x.isdigit() or x == '-']) == len(token)


def reformat_amr(input_file):
    '''Reformat AMRs -- go from single line to indented AMR on multiple lines'''
    fixed_amrs = []

    # Loop over input file with one AMR per line
    for line in open(input_file, 'r'):
        tokenized_line = tokenize_line(line).split()
        num_tabs = 0
        amr_string = []
        # Loop over parts of tokenized line
        for count, part in enumerate(tokenized_line):
            if part == '(':
                num_tabs += 1
                amr_string.append(part)
            elif part == ')':
                num_tabs -= 1
                amr_string.append(part)
            elif part.startswith(':'):
                try:
                    # Variable coming up
                    if tokenized_line[count+3] == '/':
                        amr_string.append('\n' + num_tabs * '\t' + part)
                    # Variable coming, add newline here
                    elif variable_match(tokenized_line[count+1]):
                        amr_string.append('\n' + num_tabs * '\t' + part)
                    else:
                        amr_string.append(part)
                except:
                    amr_string.append(part)
            else:
                amr_string.append(part)

        original_line = reverse_tokenize(" ".join(amr_string))
        original_line = original_line.replace('_ (', '_(').replace(') "', ')"')
        fixed_amrs.append(original_line + '\n\n')
    return fixed_amrs


if __name__ == "__main__":
    args = create_arg_parser()
    fixed_amrs = reformat_amr(args.input_file)
    # Check if AMRs are valid, error if they're not
    if args.valid:
        for amr in fixed_amrs:
            if not valid_amr(amr):
                raise ValueError(amr)
    write_to_file(fixed_amrs, args.input_file + args.extension, extra_newline=True)

