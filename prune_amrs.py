#!/usr/bin/env python
# -*- coding: utf8 -*-

'''Script that removes duplicate output from output AMRs. Most code is from best_amr_permutation.py.
    It removes nodes with same argument + concept under the same parent.
    Also removes nodes that occur three times or more, no matter the parent.

    Sample input:

    (e / establish-01 :ARG1 (m / model :mod (i / innovate-01 :ARG1 (i2 / industry) :ARG1 (i3 / industry) :ARG1 (i4 / industry))))

    Sample output:

    (e / establish-01 :ARG1 (m / model :mod (i / innovate-01 :ARG1 (i2 / industry))))

    ARG1 - industry node occurs 3 times and therefore gets pruned twice in this example.'''


import re
import sys
import argparse
import os
from amr_utils import count_not_between_quotes, write_to_file
from best_amr_permutation import get_permutations, get_best_perm, create_final_line


def create_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--input_file", required=True, type=str, help="File with AMRs (one line)")
    parser.add_argument("-c", "--cut_off", default=15, type=int, help="When to cut-off number of permutations")
    args = parser.parse_args()
    return args


def restore_variables(input_file, filtered_amrs):
    '''Restore the removed variables for the pruned file'''
    # Write variable-less AMRs to file
    write_to_file(filtered_amrs, input_file + '.pruned_temp')
    # Then restore the AMR
    os.system('python3 restoreAMR/restore_amr.py -f {0} -o {1}'.format(input_file + '.pruned_temp', input_file + '.pruned'))
    # Remove temp file again
    os.system("rm {0}".format(input_file + '.pruned_temp'))


def prune_file(input_file, cut_off):
    '''Prune input file for duplicate input'''
    filtered_amrs = []
    changed = 0

    for line in open(input_file, 'r'):
        # Delete variables from line
        clean_line = re.sub(r'\([A-Za-z0-9-_~]+ / ', r'(', line).strip()

        # Only try to do something if we can actually permute
        if count_not_between_quotes(':', clean_line) > 1:
            # Get initial permutations
            permutations, keep_string1, all_perms = get_permutations(clean_line, 1, [], 'prune', cut_off)
            keep_str = '(' + keep_string1
            # Prune duplicate output here
            final_string = get_best_perm(permutations, keep_str, all_perms, 'prune', cut_off)

            # Create final AMR line
            add_to = " ".join(create_final_line(final_string).split())
            clean_line = " ".join(clean_line.split())
            filtered_amrs.append(add_to)

            # Keep track of number of pruned AMRs
            if add_to != clean_line:
                changed += 1
        else:
            filtered_amrs.append(clean_line.strip())

    # Restore variables and write to file
    restore_variables(input_file, filtered_amrs)
    print('Changed {0} AMRs by pruning'.format(changed))


if __name__ == '__main__':
    args = create_arg_parser()
    prune_file(args.input_file, args.cut_off)


