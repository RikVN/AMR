#!/usr/bin/env python
# -*- coding: utf8 -*-

'''Scripts that sets input files in char-level
   Possible to keep structure words as single "char", e.g. :domain, :ARG1, :mod, etc
   Is able to handle POS-tags in data - processing them as a single entity

   Input should be one AMR or sentence per line

   Sample input (AMR file):

   (establish-01 :ARG1 (model :mod (innovate-01 :ARG1 (industry))))

   Sample output (AMR file):

   ( e s t a b l i s h - 0 1 + :ARG1 + ( m o d e l + :mod + ( i n n o v a t e - 0 1 + :ARG1 + ( i n d u s t r y ) ) ) )'''


import sys
import re
import argparse
import os
from amr_utils import write_to_file


def create_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--input_file', required=True, type=str, help="Input AMR file or folder")
    parser.add_argument('-fol', '--folder', action='store_true', help='Add to do multiple files in a folder - if not, args.f is a file')
    parser.add_argument('-sen', "--sent_ext", default='.sent', type=str, help="Input extension of AMRs (default .sent)")
    parser.add_argument('-a', '--amr_ext', default='.tf', type=str, help="Output extension of AMRs (default .tf)")
    parser.add_argument('-s', '--super_chars', action='store_true', help='Adding super characters for AMR files')
    parser.add_argument('-c', '--coreference', action='store_true', help='If there is path-coreference or index-coreference in the input')
    parser.add_argument('-p', '--pos', action='store_true', help='Whether input is POS-tagged')
    args = parser.parse_args()
    return args


def get_fixed_lines(file_lines, coreference):
    '''Fix lines, filter out non-relation and put back coreference paths'''

    fixed_lines = []

    for line in file_lines:
        spl = line.split()
        for idx, item in enumerate(spl):
            if len(item) > 1 and item[0] == ':':
                # Filter out non-structure words, due to links etc
                if any(x in item for x in [')', '<', ')', '>', '/', 'jwf9X']):
                    new_str = ''
                    for ch in item:
                        new_str += ch + ' '
                    spl[idx] = new_str.strip()
        fixed_lines.append(" ".join(spl))

    # Step that is coreference-specific: change | 1 | to |1|, as to not treat the indexes as normal numbers, but as separate super characters
    # Also change * 1 * to *1* and * 1 2 * to *12*
    if coreference:
        new_lines = []
        for l in fixed_lines:
            new_l = re.sub(r'\| (\d) \|', r'|\1|', l)
            new_l = re.sub(r'\* (\d) \*', r'*\1*', new_l)
            new_l = re.sub(r'\* (\d) (\d) \*', r'*\1\2*', new_l)
            new_lines.append(new_l)
        return new_lines
    else:
        return fixed_lines


def get_amr_lines(f_path):
    '''Put AMR lines in character-level format'''
    file_lines = []
    for line in open(f_path, 'r'):
        # Replace actual spaces with '+'
        line = line.replace(' ', '+')
        new_l = ''
        add_space = True
        for idx, ch in enumerate(line):
            # After ':' there should always be a letter, otherwise it is some URL probably and we just continue
            if ch == ':' and line[idx+1].isalpha():
                add_space = False
                new_l += ' ' + ch
            elif ch == '+':
                add_space = True
                new_l += ' ' + ch
            else:
                if add_space:
                    new_l += ' ' + ch
                else:
                    # We previously saw a ':', so we do not add a space
                    new_l += ch
        file_lines.append(new_l)
    return file_lines


def process_pos_tagged(f_path):
    '''Process a POS-tagged sentence file'''
    fixed_lines = []

    for line in open(f_path, 'r'):
        new_l = ''
        no_spaces = False
        # Replace actual spaces with '+'
        line = line.replace(' ', '+')
        for idx, ch in enumerate(line):
            if ch == '|':
                # Skip identifier '|' in the data
                no_spaces = True
                new_l += ' '
            elif ch == ':' and line[idx-1] == '|':
                # Structure words are also chunks
                no_spaces = True
            elif ch == '+':
                no_spaces = False
                new_l += ' ' + ch
            elif no_spaces:
                # Only do no space when uppercase letters (VBZ, NNP, etc), special case PRP$    (not necessary)
                new_l += ch
            else:
                new_l += ' ' + ch
        fixed_lines.append(new_l)
    return fixed_lines


def char_level_file(input_file, amr_ext, sent_ext, pos, super_chars, coreference):
    '''Given an input file, put it in char-level format and write output'''
    if input_file.endswith(amr_ext):
        # File ends with AMR extension, do AMR char-level processing
        out_f = input_file.replace(amr_ext, '.char' + amr_ext)

        if super_chars:
            # Super characters get a different treatment
            print('AMR file, super characters')
            amr_lines = get_amr_lines(input_file)
            fixed_lines = get_fixed_lines(amr_lines, coreference)
            write_to_file(fixed_lines, out_f)
        else:
            print('AMR file, no super characters')
            # If there are no super character we can just process with sed
            os_call = 'sed -e "s/\ /+/g"  -e "s/./&\ /g" < {0} > {1}'.format(input_file, out_f)
            os.system(os_call)

    elif input_file.endswith(sent_ext):
        # File ends with sent ext, do sentence processing
        out_f = input_file.replace(sent_ext, '.char' + sent_ext)
        if pos:
            # POS-tagged files get a different treatment
            print('Sentence file, POS-tagged')
            lines = process_pos_tagged(input_file)
            write_to_file(lines, out_f)
        else:
            # Not POS-tagged, so we can just use sed
            print('Sentence file, not POS-tagged')
            os_call = 'sed -e "s/\ /+/g"  -e "s/./&\ /g" < {0} > {1}'.format(input_file, out_f)
            os.system(os_call)

if __name__ == '__main__':
    args = create_arg_parser()

    if not args.folder:
        # Do a single file
        char_level_file(args.input_file, args.amr_ext, args.sent_ext, args.pos, args.super_chars, args.coreference)
    else:
        # Do all files in a folder with certain extension
        for root, dirs, files in os.walk(args.input_file):
            for f in files:
                if f.endswith(args.amr_ext) or f.endswith(args.sent_ext):
                    char_level_file(os.path.join(root, f), args.amr_ext, args.sent_ext, args.pos, args.super_chars, args.coreference)

