#!/usr/bin/env python
# -*- coding: utf8 -*-

'''Script that augments the data to get the best AMR permutation based on word order
   INPUT SHOULD INCLUDE ALIGNMENTS

   It outputs the normal variable-free AMR as well as the best AMR permutation. Each AMR on a single line.

   Sample input:

    # ::id PROXY_AFP_ENG_20071228_0377.18 ::amr-annotator SDL-AMR-09 ::preferred
    # ::tok Opium is the raw material used to make heroin .
    # ::alignments 0-1.2 1-1.2.r 3-1.1 4-1 5-1.3 7-1.3.1 8-1.3.1.1
    (m / material~e.4
          :mod (r / raw~e.3)
          :domain~e.1 (o / opium~e.0)
          :ARG1-of (u / use-01~e.5
                :ARG2 (m2 / make-01~e.7
                      :ARG1 (h / heroin~e.8)
                      :ARG2 o)))

   Sample output best order (note that some nodes are swapped!):

   (material :domain (opium) :mod (raw) :ARG1-of (use-01 :ARG2 (make-01 :ARG2 (opium) :ARG1 (heroin))))

   Sample output sent:

   Opium is the raw material used to make heroin .'''

import sys
import re
import argparse
from random import shuffle
from amr_utils import write_to_file
from var_free_amrs import delete_wiki, delete_amr_variables, single_line_convert, remove_char_outside_quotes


def create_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--input_file", required=True, type=str, help="folder that contains to be processed files")
    parser.add_argument("-a", "--amr_ext", default='.txt', type=str, help="AMR extension (default .txt) - should have alignments")
    parser.add_argument("-c", "--cut_off", default=15, type=int, help="When to cut-off number of permutations")
    parser.add_argument("-d", "--double", action='store_true', help="Add best permutation AMR AND normal AMR")
    args = parser.parse_args()
    return args


def get_tokenized_sentences(f):
    '''Get sentences from AMR file'''
    sents = [l.replace('# ::snt', '').replace('# ::tok', '').strip() for l in open(f, 'r') if l.startswith('# ::snt') or l.startswith('# ::tok')]
    return sents


def remove_alignment(string):
    '''Function that removes alignment information from AMR'''
    string = re.sub(r'~e\.[\d,]+', '', string)
    return string


def get_word_and_sense(line):
    '''Character based extraction because I couldn't figure it out using regex'''
    quotes = 0
    adding = False
    comb = []
    word = ''
    if '"' in line:
        for idx, ch in  enumerate(line):
            if ch == '"':
                quotes += 1
                if quotes % 2 != 0:
                    adding = True
                else:
                    # Finished quotations
                    comb.append([word])
                    word = ''
                    adding = False
            elif ch == '~':
                if adding:
                    word += ch
                elif ':op' in "".join(line[idx-4:idx-1]):
                    # Bugfix for strange constructions, e.g. name :op1~e.4 "Algeria"~e.2
                    continue
                else:
                    if idx+4 < len(line):
                        sense_line = line[idx+1] + line[idx+2] + line[idx+3] + line[idx+4]
                    else:
                        sense_line = line[idx+1] + line[idx+2] + line[idx+3]
                    sense = int("".join([s for s in sense_line if s.isdigit()]))
                    try:
                        comb[-1].append(sense)
                    except:
                        pass
            else:
                if adding:
                    word += ch
                else:
                    continue
    elif ':op' not in line:
        return [['', '']]
    else:
        try:
            tmp = line.split()[2]
            sense, word = get_sense(tmp)
            comb = [[word, sense]]
        except:
            print('Strange occurrence in AMR, ignore')
            return [['', '']]
    return comb


def get_sense(word):
    '''Function that gets the sense of a certain word in aligned AMR'''
    if '~' in word:
        # Extract 16 in e.g. house~e.16
        sense = word.split('~')[-1].split('.')[-1]
        if ',' in sense:
            # Some amr-words refer to multiple tokens. If that's the case, we take the average for calculating distance
            # Although this means that the actual sense does not refer to the tokens anymore
            # e.g. the sense of house~e.4,12 becomes 8
            sense = round((float(sum([int(i) for i in sense.split(',')]))) / (float(len(sense.split(',')))), 0)
        else:
            sense = int(sense)
        # Remove sense information to process rest of the word
        word = word.split('~')[0]
    else:
        sense = ''
    return sense, word


def find_words(line):
    '''Finds all words in the AMR structure'''
    comb = []
    spl_line = line.split('(')
    if '(' not in line:
        if line.count('~') > 0 and len(line.split()) > 1:
            sense, word = get_sense(line.split()[1])
            return [[word, sense]]
        else:
            return [['none-found', 0]]
    else:
        for idx in range(1, len(spl_line)):
            if spl_line[idx]:
                word = spl_line[idx].strip().split()[0].replace(')', '')
                # Name gets special treatment by AMRs
                if word == 'name':
                    cut_word = spl_line[idx].split(')')[0]
                    comb += get_word_and_sense(cut_word)
                else:
                    sense, word = get_sense(word)
                    num_digits = sum(c.isdigit() for c in word)
                    # Tricky: we want to change break-01 to break, but do not want to screw up dates (08-09-2016 or 28-10)
                    if word.count('-') == 1 and num_digits < 3 and num_digits > 0:
                        word = word.split('-')[0]
                    comb.append([word, sense])

    # Add empty sense if needed
    for idx, value in enumerate(comb):
        if len(value) < 2:
            comb[idx].append('')
    return comb


def matching_words(permutations):
    '''Finds all words in different order for all the permutations'''
    all_found = []
    for per in permutations:
        found_words = find_words(per)
        if found_words:
            all_found.append(find_words(per))
    return all_found


def calc_distance(l):
    '''Calculates distance between list items in two lists'''
    # l needs to start from zero, get lowest number and substract it from all numbers
    min_l = min([int(x[1]) for x in l if x[1] != ''])
    l = [[x[0], (x[1] - min_l)] for x in l if x[1] != '']
    distance = 0
    for idx, item in enumerate(l):
        # Check if we found a sense
        if len(item) > 1 and item[1] != '':
            # Check how far away we are in our token list
            diff = abs(item[1] - idx)
            distance += diff
    return distance


def do_swap(w_list1, w_list2):
    '''Checks if we should swap two list items'''
    distance_now = calc_distance(w_list1 + w_list2)
    distance_swap = calc_distance(w_list2 + w_list1)
    return distance_now > distance_swap


def filter_colons(part):
    '''Funtion to filter out timestamps (e.g. 08:30) and websites (e.g. http://site.com)'''
    new_parts = []
    split_part = part.split(':')
    for idx in range(0, len(split_part)):
        if idx == 0:
            new_parts.append(split_part[idx])
        elif split_part[idx][0].isalpha():
            new_parts.append(split_part[idx])
        else:
            # Not actually a new part, just add to last one
            new_parts[-1] += ':' + split_part[idx]
    return new_parts


def bracket_in_string(line):
    '''Check if there are no brackets in a string
       NOTE: between quotes does not count'''
    between_quotes = False
    for char in line:
        if char == '"':
            between_quotes = not between_quotes
        elif char in ['(', ')'] and not between_quotes:
            return True
    return False


def get_add_string(search_part):
    '''Get the initial permutations and add_string'''
    paren_count = 0
    start_adding = False
    permutations = []
    add_string = ''
    between_quotes = False

    for idx, ch in enumerate(search_part):
        if ch == '(' and not between_quotes:
            if start_adding:
                add_string += ch
            paren_count += 1
        elif ch == ':' and not between_quotes:
            start_adding = True
            add_string += ch
        elif ch == ')' and not between_quotes:
            paren_count -= 1
            if start_adding:
                add_string += ch
            if paren_count == 0:
                permutations.append(add_string.strip())
                add_string = ''
        elif start_adding:
            add_string += ch
        # Keep track of quotes
        if ch == '"':
            between_quotes = not between_quotes

    # Fix parentheses
    if add_string and ':' in add_string:
        permutations.append(remove_char_outside_quotes(add_string, ')').strip())
        for idx, p in enumerate(permutations):
            while permutations[idx].count(')') < permutations[idx].count('('):
                permutations[idx] += ')'

    # Permutate without brackets (e.g. :op1 "name1" :op2 "name2" :op3 "name3" etc
    for p in permutations:
        if not bracket_in_string(p):
            if p.count(':') > 2:
                p_split = p.split(':')[1:]
                new_perms = [':' + x.strip() for x in p_split]
                return add_string, new_perms
    return add_string, permutations


def get_keep_string(new_parts, level):
    '''Obtain string we keep, it differs for level 1'''
    if level > 1:
        keep_string = ':' + ":".join(new_parts[:1])
    else:
        keep_string = ":".join(new_parts[:1])
    search_part = ':' + ":".join(new_parts[1:])
    return keep_string, search_part


def combine_permutations(permutations, cut_off):
    '''Combine permutations if they exceed the cut-off specified'''
    if len(permutations) > cut_off:
        shuffle(permutations)
        # Add extra permutations to the last permutation
        # to avoid losing information
        permutations = permutations[0:cut_off - 1] + [" ".join(permutations[cut_off - 1:])]
    return permutations


def change_possible(part):
    '''Check if there is anything to permute'''
    if ':' not in part or (part.count(':') == 1 and ('http:' in part or 'https:' in part)):
        return False
    else:
        return True


def get_permutations(part, level, all_perms, type_script, cut_off):
    '''Function that returns the permutations in the best order'''
    # Make life easier by skipping first '(' or ':'
    part = part[1:]

    # If there is nothing to change then we return
    if not change_possible(part):
        if level == 1:
            return [part], '', all_perms
        else:
            return [':' + part], '', all_perms

    # Remove non-arguments that have a colon such as timestamps and websites
    new_parts = filter_colons(part)
    # Find the part of the string we keep
    keep_string, search_part = get_keep_string(new_parts, level)
    # Get the initial permutations
    _, permutations = get_add_string(search_part)

    # Check the cut_off so that we don't do more permutations than we want
    permutations = combine_permutations(permutations, cut_off)
    # Find the list of lists that contain word-sense pairs
    word_list = matching_words(permutations)

    # Two possibilities here, ordering or pruning. This script only does ordering,
    # but prune_amrs.py does pruning and uses this function as well
    if type_script == 'prune':
        permutations_set = []
        for p in permutations:
            # Remove all nodes with same parent
            if p in permutations_set:
                continue
            elif p not in all_perms:
                permutations_set.append(p)
            elif all_perms.count(p) < 2:
                # If we saw the node twice, stop adding
                permutations_set.append(p)
            all_perms.append(p)
        return permutations_set, keep_string, all_perms
    else:
        if len(word_list) != len(permutations):
            # Something strange is going on here, just ignore it and do nothing to avoid errors
            print('Strange AMR part')
            all_perms += permutations
            return permutations, keep_string, all_perms
        else:
            for p in range(len(permutations)):
                for idx in range(len(permutations)-1):
                    # Permuting takes place here, check if swapping results in better order
                    if do_swap(word_list[idx], word_list[idx+1]):
                        permutations[idx], permutations[idx+1] = permutations[idx+1], permutations[idx]
                        word_list[idx], word_list[idx+1] = word_list[idx+1], word_list[idx]
            all_perms += permutations
            return permutations, keep_string, all_perms


def do_string_adjustments(permutations_new, keep_string2):
    '''Make sure the string is correct'''
    add_string = keep_string2 + ' ' + " ".join(permutations_new) + ' '

    # Check if we need to add a parenthesis
    while add_string.count(')') < add_string.count('('):
        # Avoid extra unnecessary space
        add_string += ')'
    return add_string


def create_final_line(final_string):
    '''Do final adjustments for line'''
    add_to = final_string.replace('  ', ' ') .strip()
    while ' )' in add_to:
        add_to = add_to.replace(' )', ')')
    # Fix parentheses and remove alignment information
    add_to = fix_paren(add_to)
    add_to = remove_alignment(add_to)
    # Fix tokenization
    add_to = add_to.replace('):', ') :').replace(' :)', ')').replace(': :', ':')
    return add_to


def fix_paren(string):
    '''Add parentheses when necessary'''
    while string.count('(') > string.count(')'):
        string += ')'
    return string


def get_best_perm(permutations, final_string, all_perms, type_script, cut_off):
    '''This must also be possible recursive - I tried...
       For each (sub)-AMR, get the best permutation based on input words'''
    for p2 in permutations:
        permutations_2, keep_string2, all_perms = get_permutations(p2, 2, all_perms, type_script, cut_off)
        for p3 in permutations_2:
            permutations_3, keep_string3, all_perms = get_permutations(p3, 3, all_perms, type_script, cut_off)
            for p4 in permutations_3:
                permutations_4, keep_string4, all_perms = get_permutations(p4, 4, all_perms, type_script, cut_off)
                for p5 in permutations_4:
                    permutations_5, keep_string5, all_perms = get_permutations(p5, 5, all_perms, type_script, cut_off)
                    for p6 in permutations_5:
                        permutations_6, keep_string6, all_perms = get_permutations(p6, 6, all_perms, type_script, cut_off)
                        for p7 in permutations_6:
                            permutations_7, keep_string7, all_perms = get_permutations(p7, 7, all_perms, type_script, cut_off)
                            for p8 in permutations_7:
                                permutations_8, keep_string8, all_perms = get_permutations(p8, 8, all_perms, type_script, cut_off)
                                for p9 in permutations_8:
                                    permutations_9, keep_string9, all_perms = get_permutations(p9, 9, all_perms, type_script, cut_off)
                                    for p10 in permutations_9:
                                        permutations_10, keep_string10, all_perms = get_permutations(p10, 10, all_perms, type_script, cut_off)
                                        for p11 in permutations_10:
                                            permutations_11, keep_string11, all_perms = get_permutations(p11, 11, all_perms, type_script, cut_off)
                                            for p12 in permutations_11:
                                                permutations_12, keep_string12, all_perms = get_permutations(p12, 12, all_perms, type_script, cut_off)
                                                add_string = do_string_adjustments(permutations_12, keep_string12)
                                                keep_string11 += add_string.replace('  ', ' ')
                                            keep_string10 += fix_paren(keep_string11)
                                        keep_string9 += fix_paren(keep_string10)
                                    keep_string8 += fix_paren(keep_string9)
                                keep_string7 += fix_paren(keep_string8)
                            keep_string6 += fix_paren(keep_string7)
                        keep_string5 += fix_paren(keep_string6)
                    keep_string4 += fix_paren(keep_string5)
                keep_string3 += fix_paren(keep_string4)
            keep_string2 += fix_paren(keep_string3)
        final_string += fix_paren(keep_string2)
    return fix_paren(final_string)


def process_file_best(amrs, sent_amrs, cut_off):
    '''Permute AMR so that it best matches the word order'''
    save_all_amrs = []

    # Sanity check
    assert len(amrs) == len(sent_amrs)

    # Loop over all AMRs and return best matching permutation
    for idx, amr in enumerate(amrs):
        # Only try to do something if we can actually permute
        if amr.count(':') > 1:
            permutations, keep_string1, _ = get_permutations(amr, 1, [], 'order', cut_off)
            final_string = get_best_perm(permutations, '(' + keep_string1, [], 'order', cut_off)
            # Save final output string
            save_all_amrs.append(create_final_line(final_string))
        else:
            # Just save AMR if there's nothing to do
            save_all_amrs.append(remove_alignment(amr))

    # Fix tokenization and remove alignment
    for idx, amr in enumerate(amrs):
        amrs[idx] = amr.replace(' )', ')')
        amrs[idx] = remove_alignment(amr)

    # Print how many AMRs we actually changed by doing this
    changed_amrs = len(amrs) -  len([i for i, j in zip(amrs, save_all_amrs) if i == j])
    print('Changed {0} out of {1} amrs'.format(changed_amrs, len(amrs)))
    return save_all_amrs, amrs


def preprocess(f_path):
    '''Preprocess the AMR file, deleting variables/wiki-links and tokenizing'''
    # Delete Wiki links from AMRs
    no_wiki_amrs = delete_wiki(f_path)
    # Remove variables from AMR
    del_amrs = delete_amr_variables(no_wiki_amrs)
    # Old amrs with deleted wiki and variables
    old_amrs, sent_amrs = single_line_convert(del_amrs, '')
    return sent_amrs, old_amrs


def create_output(input_file, old_amrs, new_amrs, sent_amrs, double, amr_ext):
    '''Print output to the correct files - also keep no-var AMR'''
    permuted_amr, no_var_amr, sent_file, double_sent_file, double_amr_file = get_filenames(input_file, amr_ext)
    write_to_file(old_amrs, no_var_amr)
    write_to_file(new_amrs, permuted_amr)
    write_to_file(sent_amrs, sent_file)
    # Potentially we want to keep BOTH the original AMR and the best-permuted AMR
    if double:
        write_to_file(old_amrs + new_amrs, double_amr_file)
        write_to_file(sent_amrs + sent_amrs, double_sent_file)


def get_filenames(input_file, amr_ext):
    '''Return list of filenames for output of this script'''
    permuted_amr = input_file.replace(amr_ext, '.tf.best')
    no_var_amr = input_file.replace(amr_ext, '.tf')
    sent_file = input_file.replace(amr_ext, '.sent')
    double_sent = input_file.replace(amr_ext, '.sent.double')
    double_amr = input_file.replace(amr_ext, '.tf.double')
    return permuted_amr, no_var_amr, sent_file, double_sent, double_amr


if __name__ == '__main__':
    args = create_arg_parser()
    sent_amrs, old_amrs = preprocess(args.input_file)
    new_amrs, old_amrs = process_file_best(old_amrs, sent_amrs, args.cut_off)
    # Write output to file
    create_output(args.input_file, old_amrs, new_amrs, sent_amrs, args.double, args.amr_ext)
