#!/usr/bin/env python3
# -*- coding: utf8 -*-

'''Script that restores AMR variables. Most of the code is from https://github.com/didzis/tensorflowAMR/tree/master/SemEval2016

Possible to restore AMRs that used the Indexing or absolute Paths method, described in "Dealing with Co-reference in Neural Semantic Parsing", Van Noord and Bos, 2017

Sample input:

( l o o k - 0 1 + :mode + i m p e r a t i v e + :ARG0 + ( y o u ) )

Sample output:

(vvlook-01 / look-01 :mode imperative :ARG0 (vvyou / you))

This script should also work for word-level input (though mostly tested on char-level)'''


import sys
import re
import random
import argparse
from amr_utils import load_dict, left_space_for_char, space_brackets_amr, is_number, remove_char_outside_quotes, tokenize_line, reverse_tokenize, write_to_file, between_quotes, replace_not_in_quotes
from best_amr_permutation import filter_colons, get_keep_string
from var_free_amrs import process_var_line


# General regex for fixing invalid AMRs
unbracket = re.compile(r'\(\s*([^():\s"]*)\s*\)[^"]')
dangling_edges = re.compile(r':[\w\-]+\s*(?=[:)])')
missing_edges = re.compile(r'(\/\s*[\w\-]+)\s+\(')
missing_variable = re.compile(r'(?<=\()\s*([\w\-]+)\s+(?=:)')
missing_quotes = re.compile(r'("\w+)(?=\s\))')
misplaced_colon = re.compile(r':(?=\))')
missing_concept_and_variable = re.compile(r'(?<=\()\s*(?=:\w+)')
dangling_quotes = re.compile(r'(?<=\s)(\w+)"(?=\s|\)|:)')


def create_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--input_file", required=True, type=str, help="File with AMRs (one line)")
    parser.add_argument("-o", "--output_file", required=True, type=str, help="Output file")
    parser.add_argument('-c', "--coreference", default='dupl', choices=['dupl', 'index', 'abs'], help='How to handle coreference - input was either duplicated/indexed/absolute path (default dupl)')
    parser.add_argument("-r", "--ref_dict", default='restoreAMR/ref_dict', type=str, help="Ref dict file")
    parser.add_argument('-p', '--print_stats', action='store_true', help='Print coreference statistics')
    args = parser.parse_args()
    return args


def preprocess(line, coreference):
    '''Preprocess line back to format without + for space. Special case:
       :polite +, we need to keep that'''
    line = line.replace(':polite +', ':polite 100')
    line = line.replace(' ', '')
    line = replace_not_in_quotes(line, '+', ' ')
    # Absolute paths need a different preprocessing step
    if coreference == 'abs':
        line = preprocess_abs(line)
    return line


def initial_check(coreference, ref_file):
    '''Do initial checks and prints, load dicts as well'''
    if coreference == 'index':
        replace_types = ['Normal case', 'Replace by variable that is not referred to', 'Replace by most frequent index', 'Replace by most frequent concept', 'No concepts found - do person']
        index_dict = dict.fromkeys(replace_types, 0)
    elif coreference == 'abs':
        replace_types = ['Path lead to variable', 'Path did not lead to variable']
        index_dict = {}
        index_dict[replace_types[0]] = []
        index_dict[replace_types[1]] = []
    else:
        index_dict = {}
        replace_types = []

    # Load dictionary with frequency information
    ref_dict = load_dict(ref_file)
    return ref_dict, index_dict, replace_types


#### General restore functions (mostly from https://github.com/didzis/tensorflowAMR/tree/master/SemEval2016)

def remove_dangling_edges(line):
    '''Remove unfinished edges (can happen with char-level output)'''
    if line[-1] != ')':
        line = ")".join(line.split(')')[:-1]) + ')'
    return line


def replace_var(m):
    global c
    global cc
    global ggg
    if ['name', 'date'].count(m.group(1)) == 1:
        c += 1
        return '(v' + str(ggg) + str(c) + ' / ' + m.group(1) + m.group(2)
    if cc.count(m.group(1)) == 0:
        cc.append(m.group(1))
        return '(vv' + str(ggg) + m.group(1) + ' / ' + m.group(1) + m.group(2)
    # Don't replace duplicates for abs/index
    if m.group(2) == ' )' and args.coreference not in ['abs', 'index']:
        return ' vv' + str(ggg) + m.group(1)
    c += 1
    return '(vvvv' + str(ggg) + str(c) + ' / ' + m.group(1) + m.group(2)


def replace_var2(m):
    if m.group(2) == "-":
        return "%s %s" % (m.group(1), m.group(2))
    if m.group(2) == "interrogative":
        return "%s %s" % (m.group(1), m.group(2))
    if m.group(2) == "expressive":
        return "%s %s" % (m.group(1), m.group(2))
    if m.group(2) == "imperative":
        return "%s %s" % (m.group(1), m.group(2))
    return "%s \"%s\"" % (m.group(1), m.group(2))


def add_quotes(m):
    value = m.group(2).strip()
    if value == '-':
        return '%s %s ' % (m.group(1), value)
    return '%s "%s" ' % (m.group(1), value)


def convert(line):
    line = line.rstrip().lstrip(' \xef\xbb\xbf\\ufeff')
    line = line.rstrip().lstrip('> ')
    line = " ".join(line.split())
    global cc
    global c
    global ggg
    c = 0
    cc = []
    old_line = line
    while True:
        line = re.sub(r'(\( ?name [^()]*:op\d+|:wiki) ([^\-_():"][^():"]*)(?=[:\)])', add_quotes, line, re.I)
        if old_line == line:
            break
        old_line = line
    # Add variables back here
    line = ' ' + line
    line = re.sub(r'[^_]\(\s*([\w\-\d]+)(\W|\))', replace_var, line)

    # Make sure parentheses match
    open_count = 0
    close_count = 0
    for i, c in enumerate(line):
        if c == '(':
            open_count += 1
        elif c == ')':
            close_count += 1
        if open_count == close_count and open_count > 0:
            line = line[:i].strip()
            break

    old_line = line
    while True:
        open_count = len(re.findall(r'\(', line))
        close_count = len(re.findall(r'\)', line))
        if open_count > close_count:
            line += ')' * (open_count-close_count)
        elif close_count > open_count:
            for i in range(close_count-open_count):
                line = line.rstrip(')')
                line = line.rstrip(' ')

        if old_line == line:
            break
        old_line = line

    old_line = line

    while True:
        line = re.sub(r'(:\w+) ([^\W\d\-][\w\-]*)(?=\W)', replace_var2, line, re.I)
        if old_line == line:
            break
        old_line = line

    # Add the extra spaces that are sometimes needed
    extra_space_needed = ['imperative', 'interrogative', 'expressive']
    for esn in extra_space_needed:
        line = line.replace(esn, ' {0} '.format(esn))

    # Fix other problems that might still be there
    line = unbracket.sub(r'\1', line, re.U)
    line = dangling_edges.sub('', line, re.U)
    line = missing_edges.sub(r'\1 :ARG2 (', line, re.U)
    line = missing_variable.sub(r'vvvx / \1 ', line, re.U)
    line = missing_quotes.sub(r'\1"', line, re.U)
    line = misplaced_colon.sub(r'', line, re.U)
    line = missing_concept_and_variable.sub(r'd / dummy ', line, re.U)
    line = dangling_quotes.sub(r'\1', line, re.U)
    return line


def add_space_when_digit(line):
    '''Add a space when see a digit, except for arguments of id_list'''
    id_list = ['ARG', 'op', 'snt', '-']

    spl = line.split(':')
    for idx in range(1, len(spl)):
        if spl[idx].strip().replace(')', ''):
            check_arg = spl[idx].replace(')', '').replace('ARG', '').strip()
            check_op = spl[idx].replace(')', '').replace('op', '').strip()
            # If there is a digit after quant or value, put a space so we don't error, e.g. :value3 becomes :value 3, but not for op, snt and ARG
            if spl[idx].strip().replace(')', '')[-1].isdigit() and (not any(x in spl[idx] for x in id_list)):
                new_string = ''
                added_space = False
                for ch in spl[idx]:
                    if ch.isdigit():
                        if not added_space:
                            new_string += ' ' + ch
                            added_space = True
                        else:
                            new_string += ch
                    else:
                        new_string += ch
                spl[idx] = new_string
            elif is_number(check_arg):                #change ARG2444 to ARG2 444
                spl[idx] = re.sub(r'(ARG\d)([\d\.]+)', r'\1 \2', spl[idx])
            elif is_number(check_op):                #change op124 to op1 24
                spl[idx] = re.sub(r'(op\d)([\d\.]+)', r'\1 \2', spl[idx])
    return ':'.join(spl)


def separate_quotes(line):
    '''Separate quotes from an argument + value, i.e.
       :op1"tom" to :op1 "tom" '''
    quotes = 0
    new_line = ''

    for ch in line:
        if ch == '"':
            quotes += 1
            if quotes % 2 != 0 and new_line[-1] != ' ':
                new_line += ' "'                            #add space for quote
            else:
                new_line += ch
        else:
            new_line += ch
    return new_line

def do_extra_steps(line):
    '''Do some extra necessary postprocessing/fixing steps'''
    # Add extra space for colons and parentheses
    line = line.replace(':', ' :')
    line = line.replace('(', ' (')

    # Make sure quotes always start with a leading space (but not end)
    line = separate_quotes(line)

    # We want to make sure that we do Wiki links correctly
    # They always look like this :wiki "link_(information)"
    new_line = line.replace('_ (', '_(').replace(') "', ')"')

    # Fix problem with op and numbers, e.g. change op123.5 to op1 23.5
    new_line = re.sub(r'(op\d)(\d\d+)', r'\1 \2', new_line)
    new_line = re.sub(r'(op\d)(\d+)\.(\d+)', r'\1 \2.\3', new_line)
    new_line = re.sub(r'(mod\d)(\d+)\.(\d+)', r'\1 \2.\3', new_line)
    new_line = re.sub(r'(ARG\d)(\d+)\.(\d+)', r'\1 \2.\3', new_line)

    # Make sure polarity and wiki links do not accidentally get removed, this will be
    # restored in a later step
    new_line = new_line.replace(':polarity-', ':polarity 100').replace(':wiki-', ':wiki "100"')
    new_line = new_line.replace(':polarity -', ':polarity 100').replace(':wiki -', ':wiki "100"')
    # Make sure that the paths are treated as separate tokens later
    new_line = re.sub(r'(\*[\d]+\*)', r' \1 ', new_line)
    return new_line


def add_coref_instance(next_items):
    '''Add coreference items that are instantiated by this:
    *0* country :wiki "possible value" :add "more_values"'''
    add_items = []
    for idx, item in enumerate(next_items):
        if item.strip()[0] in [')', '(']:
            # We are done with adding, return
            return remove_char_outside_quotes("-----".join(add_items), ')')
        elif item.startswith(':'):
            # Only add this item if next one is a constant, i.e. between quotes or number
            # If not, we stop
            if idx + 1 < len(next_items) and (is_number(next_items[idx+1]) or between_quotes(next_items[idx+1])):
                add_items.append(item)
            else:
                return remove_char_outside_quotes("-----".join(add_items), ')')
        else:
            add_items.append(item)
    # If we never returned perhaps we were at the end with content (AMR is not valid then though)
    # Just return items we have so far
    if add_items:
        return remove_char_outside_quotes("-----".join(add_items), ')')
    # Just a reference, not an instantiation
    else:
        return ''


def restore_coref_indexing(line, ref_dict):
    '''Restore coreference items, e.g. *3* and *2* with actual word'''
    pattern = re.compile(r'^\*[\d]+\*$')
    # Make sure coref indexes are separate
    tok_line = line.split()
    seen_coref = {}
    new_tok = []

    # First find all instantiated indexes
    for idx, item in enumerate(tok_line):
        if pattern.match(item):
            if idx < len(tok_line) -1:
                instant_value = add_coref_instance(tok_line[idx+1:])
                # Only add if it actually was an instantiation
                if instant_value:
                    seen_coref[item] = instant_value

    for idx, item in enumerate(tok_line):
        # Check if we have a match for a index variable
        if pattern.match(item):
            # Can't look ahead to idx + 1 here
            if idx == len(tok_line) -1:
                referent = get_most_frequent_word(tok_line, ref_dict)
                new_tok.append('(coref-{0})'.format(referent))
            # Instantiated case, just removing index is enough
            # I.e. *0* work, we remove the *0* and just keep work
            elif tok_line[idx+1][0].isalpha():
                pass
            # Replace coref instance
            else:
                if item in seen_coref:
                    # Normal case, reference to instantiated index
                    referent = seen_coref[item]
                    index_dict[replace_types[0]] += 1
                # Problem: we have an index but it was never instantiated
                else:
                    # Solution: add most frequent other referent (most rather have one that was never instantiated),
                    # if they are all not in train set add one at random
                    if len(seen_coref) > 0:
                        referent = get_most_frequent_referent(seen_coref, ref_dict, tok_line)
                    # If there are no other referents just add the most frequent one in general based on all words in sentence
                    else:
                        referent = get_most_frequent_word(tok_line, ref_dict)
                # Hacky: we have no variables here, we need to recognize that we need to replace this word in a later stage without
                # messing up the restoring variables process. We also add unneccesary brackets to not mess up the variable restoring
                # process, we remove them in a later stage as well
                new_tok.append('(coref-{0})'.format(referent))
        else:
            new_tok.append(item)

    # Fix some tokenization problems again
    new_line = " ".join(new_tok)
    while ' )' in new_line or '( ' in new_line:
        new_line = new_line.replace(' )', ')').replace('( ', '(')
    return new_line


def get_most_frequent_word(tok_line, ref_dict):
    '''Function that returns the concept in the AMR (tok_line) that is most frequently a referent in the training set (ref_dict)'''
    most_freq, score = '', -1
    words = []

    # Collect frequency information
    for item in tok_line:
        if item[0].isalpha():
            words.append(item)
            if item in ref_dict:
                if ref_dict[item] > score:
                    score = ref_dict[item]
                    most_freq = item

    if score > -1:
        # Return word that most often has a referent in training set
        index_dict[replace_types[3]] += 1
        return most_freq
    elif words:
        # No known words from our training set, return random one, last one might be cut-off though so ignore that one
        index_dict[replace_types[3]] += 1
        rand_return = random.choice(words[0:-1]) if len(words) > 1 else random.choice(words)
        return rand_return
    else:
        # If all else fails just return person
        index_dict[replace_types[4]] += 1
        return 'person'


def get_most_frequent_referent(seen_coref, ref_dict, tok_line):
    '''Takes care of indexes that were never instantiated'''

    # First check if we have instantiated variables that were never referred to
    line = " ".join(tok_line)
    most_freq = ''
    score = -1

    for item in seen_coref:
        # Index only occurs once - never used as reference
        if line.count(item) == 1:
            # If this word in general dict, check if it is the most frequent
            if seen_coref[item] in ref_dict:
                if ref_dict[seen_coref[item]] > score:
                    score = ref_dict[seen_coref[item]]
                    most_freq = seen_coref[item]
            else:
                most_freq = seen_coref[item]
                score = 0

    # If we found once, return that one
    if score > -1:
        index_dict[replace_types[1]] += 1
        return most_freq
    # Else find the most frequent in general
    else:
        most_freq = ''
        score = -1
        # If this word in general dict, check if it is the most frequent
        for item in seen_coref:
            if seen_coref[item] in ref_dict:
                if ref_dict[seen_coref[item]] > score:
                    score = ref_dict[seen_coref[item]]
                    most_freq = seen_coref[item]

        if score > -1:
            # Return most frequent referent we saw
            index_dict[replace_types[2]] += 1
            return most_freq
        else:
            # If no referents with score, return a random one
            index_dict[replace_types[2]] += 1
            rand_key = random.choice(list(seen_coref.keys()))
            return seen_coref[rand_key]


def add_coref(line):
    '''Do the replacement; line includes variables, but we still need to replace 'COREF-person' with 'p', for example'''
    var_dict = {}
    tok_line = space_brackets_amr(line).split()

    # Get variable-value pairs first
    for idx, item in enumerate(tok_line):
        # Variable in previous tok and value in tok afterwards
        if item == '/':
            if 'coref-' not in tok_line[idx+1]:
                value = add_coref_instance(tok_line[idx+1:])
                var_dict[value] = tok_line[idx-1]

    # Add back the coreference here
    new_tok = []
    ignore_next = False
    for idx, item in enumerate(tok_line):       #add coref back
        if item.startswith('coref-'):
            ignore_next = False
            it = item.replace('coref-', '')
            if it in var_dict:
                new_tok.append(var_dict[it].replace('-----', ' '))
                # Remove previous 3 items, " ( var / " and next item " ) "
                new_tok[-2], new_tok[-3], new_tok[-4] = '', '', ''
                ignore_next = True
            else:
                # If the reference is unknown, just add person
                new_tok.append('person')
                new_tok[-2], new_tok[-3], new_tok[-4] = '', '', ''
                ignore_next = True
        elif not ignore_next:
            new_tok.append(item)
            ignore_next = False
        else:
            ignore_next = False

    # Join back the line and return in format we expect later
    new_line = " ".join(new_tok)
    return reverse_tokenize(new_line)


def preprocess_abs(line):
    '''Put in such a format that restoring still works'''
    # First restore the general format we expect, make sure there are spaces
    # between all our information carrying tokens
    new_line = left_space_for_char(space_brackets_amr(line), ':')
    new_line = " ".join(new_line.replace('}', ' } ').replace('{', ' { ').split())
    new_line = re.sub(r'(\|[\d]+\|)', r' \1 ', new_line)
    new_line = " ".join(new_line.split())

    # Rewrite the absolute paths to coref links so we can restore the coreference later
    # without the convert() function messing everything up
    if '{' in new_line:
        line_parts = []
        coref_parts = []
        coref = False
        for item in new_line.split():
            if item == '{':
                # Add brackets to keep structure
                line_parts.append('(')
                coref = True
            elif item == '}':
                add_part = 'COREF*' + "*".join(coref_parts).replace(':', 'COLON')
                line_parts.append(add_part)
                line_parts.append(')')
                coref = False
                coref_parts = []
            elif coref:
                coref_parts.append(item)
            else:
                line_parts.append(item)
        return " ".join(line_parts)
    else:
        return line


def replace_absolute_paths(line, ref_dict):
    '''Replace absolute paths by the correct variable referent'''
    # Put line in format we expect
    spl_line = tokenize_line(line).split()
    new_line = line

    # Loop over line and find the replacement for the coreference items
    for idx, item in enumerate(spl_line):
        if 'COREF*' in item:
            # Find actual replacement here
            repl = find_replacement(line, item, ref_dict)
            if repl:
                # Replace this part with the reference
                to_be_replaced = " ".join(spl_line[idx-3:idx+2])
            else:
                # Remove reference, so also include the argument
                to_be_replaced = " ".join(spl_line[idx-4:idx+2])

            new_line = tokenize_line(new_line)
            # Do actual replacement here (adding coreference)
            new_line = new_line.replace(to_be_replaced, repl)
    return reverse_tokenize(new_line)


def find_replacement(line, item, ref_dict):
    '''Find variable replacement for the path described in the output'''
    line = " ".join(space_brackets_amr(line).split())

    # We made temporary changes before as to not mess up the AMR, put those back first
    path = item.replace('COREF', '').replace('COLON', ':').replace('*', ' ').strip()

    # Differentiate between arguments and number of arguments
    args = [x for idx, x in enumerate(path.split()) if idx % 2 == 0]
    num = [x for idx, x in enumerate(path.split()) if idx % 2 != 0]
    nums = [int(x.replace('|', '').strip()) for x in num]

    # Find the concepts in this AMR
    concept_dict = get_concepts(line)

    # Remove non-arguments that have a colon such as timestamps and websites
    tok_line = " ".join(line.split())
    new_parts = filter_colons(tok_line)

    # Find the part we have to search
    _, search_part = get_keep_string(new_parts, 0)

    # Check if we found a correct path for this AMR
    path_found, search_part = possible_path(args, nums, search_part)

    # If we found correct path, return it
    if path_found:
        index_dict[replace_types[0]].append(path)
        return get_reference(search_part)
    # Else return the variable the is most frequently a referent in the training set (default)
    else:
        index_dict[replace_types[1]].append(path)
        return most_frequent_var(concept_dict, ref_dict)


def get_path_to_search(search_part):
    '''Find the path that we will search for this AMR'''
    add_str, cur_rel, prev_rel, add_cur_rel, start_adding = '', '', '', False, False

    for ch in search_part:
        if ch == ':':
            add_cur_rel = True
            cur_rel = ':'
            if start_adding:
                add_str += ch
        elif ch == '(':
            start_adding = True
            add_str += ch
        elif start_adding:
            add_str += ch
        elif ch == ' ':
            prev_rel = cur_rel
            cur_rel = ''
            add_cur_rel = False
        elif add_cur_rel:
            cur_rel += ch
    return prev_rel + ' ' + add_str


def get_permutations_by_string(search_part, level):
    '''Get the initial permutations and add_string'''

    paren_count = 0
    start_adding = False
    permutations = []
    add_string = ''

    if level > 0:
        search_part = ':' + ":".join(search_part.split(':')[2:])
        search_part = get_path_to_search(search_part)

    # Make sure to handle some special cases
    num_pattern = re.compile(r':[a-zA-Z0-9]+[ ]+(-\d+|\d+|imperative|interrogative|expressive|-)')
    li_pattern = re.compile(r':li+[ ]+"[A-Za-z-0-9]+"')

    # Remove double spaces from search part
    search_part = " ".join(search_part.split())

    for idx, ch in enumerate(search_part):
        if ch == '(':
            if start_adding:
                add_string += ch
            paren_count += 1
        elif ch == ':':
            start_adding = True
            add_string += ch
        elif ch == ')':
            paren_count -= 1
            if start_adding:
                add_string += ch
            if paren_count == 0:
                permutations.append(add_string.strip())
                add_string = ''
        elif start_adding:
            add_string += ch
        # Special case, numbers such as :li 2 and :quant 300 mess everything up, or :mode imperative
        if idx != len(search_part) -1 and (num_pattern.match(add_string.strip()) or li_pattern.match(add_string.strip())) and not search_part[idx+1].isdigit():
            # Then just add permutation now already and continue
            permutations.append(add_string.strip())
            add_string = ''

    # Check the final string we have left as well
    if add_string and ':' in add_string:
        permutations.append(add_string.replace(')', '').strip())
        for idx, p in enumerate(permutations):
            while permutations[idx].count(')') < permutations[idx].count('('):
                permutations[idx] += ')'


    # Permute without brackets (e.g. :op1 "name1" :op2 "name2" :op3 "name3"
    for p in permutations:
        if ')' not in p or '(' not in p:
            if p.count(':') > 2:
                p_split = p.split(':')[1:]
                new_perms = [':' + x.strip() for x in p_split]
                return add_string, new_perms

    return add_string, permutations


def get_concepts(line):
    '''Function that returns AMR concepts while restoring for the paths method'''
    line = " ".join(line.split())
    _, var_dict = process_var_line(line, {})

    for key in var_dict:
        spl = var_dict[key].split()
        if spl[-1].startswith(':'):
            # Solve problems with everything being in one line, e.g. change concept :ARG1 to just concept
            var_dict[key] = " ".join(spl[0:-1])
    return var_dict


def restore_rewrites(line):
    '''Restore rewrites we did for wiki - , polarity - and polite +'''
    line = " ".join(line.split())
    line = line.replace(':polarity 100', ':polarity -').replace(':wiki "100"', ':wiki -').replace(":polite 100", ":polite +")
    line = line.replace('http ://', 'http://')
    # Fix problem with clocktimes: e.g. " 07 :00" becomes "07:00"
    line = re.sub(r' ([\d])+ :([\d]+)', r'\1:\2', line)
    return line

def possible_path(args, nums, search_part):
    '''Function that returns whether it is possible to follow the path to a referent'''
    path_found = True
    for idx in range(0, len(args)):
        _, permutations = get_permutations_by_string(search_part, idx)
        # Check if the output path matches with a path in the AMR
        search_part = matching_perm(permutations, args[idx], nums[idx])
        if not search_part:
            # Did not find a correct path
            path_found = False
            break
    return path_found, search_part


def matching_perm(permutations, rel, count):
    '''Check if the current path value matches a possible path in the AMR'''
    num_matches, matching_perm = 0, ''
    for p in permutations:
        rel_p = p.split()[0]
        if rel_p == rel:
            num_matches += 1
            if num_matches == count:
                matching_perm = p
    return matching_perm


def get_reference(search_part):
    '''Get the correct reference'''
    spl_line = search_part.split()
    for idx, part in enumerate(spl_line):
        if part == '/':
            ref_var = spl_line[idx-1]
            break
    return ref_var.replace('(', '')


def most_frequent_var(concept_dict, ref_dict):
    '''Get the variable in AMR that is most frequent in training set, based on dictionary of concepts'''
    most_freq, score = '', -1
    for item in concept_dict:
        if concept_dict[item] in ref_dict:
            if ref_dict[concept_dict[item]] > score:
                score = ref_dict[concept_dict[item]]
                most_freq = item

    if score == -1:
        # No best score found, just return random
        return random.choice(list(concept_dict.keys()))
    else:
        return most_freq


def print_coref_stats(coreference, replace_types, index_dict):
    '''Print some statistics of how we handled coreference (for indexing and absolute method)'''
    if coreference == 'index':
        print('Results for types of replacements:\n')
        for key in replace_types:
            print('{0}: {1}'.format(key, index_dict[key]))
    elif coreference == 'abs':
        for idx in range(1, 4):
            for key in replace_types:
                # Only get paths of certain length
                cur_paths = [x for x in index_dict[key] if (len(x.split()) / 2) == idx]
                print(key)
                print('Len cur_paths: {0} for idx {1}\n'.format(len(cur_paths), idx))
        # All paths
        for key in replace_types:
            cur_paths = [x for x in index_dict[key] if (len(x.split()) / 2) > 0]
            print(key)
            print('Len cur_paths: {0} for idx {1}\n'.format(len(cur_paths), 0))
        # All longer paths
        for key in replace_types:
            cur_paths = [x for x in index_dict[key] if (len(x.split()) / 2) > 3]
            print(key)
            print('Len cur_paths: {0} for idx {1}\n'.format(len(cur_paths), '>3'))

if __name__ == '__main__':
    args = create_arg_parser()
    # Check parser arguments and load reference dict
    ref_dict, index_dict, replace_types = initial_check(args.coreference, args.ref_dict)
    restored_lines = []

    global ggg
    ggg = 0

    # Loop over all AMRs in a file (one per line!)
    for idx, line in enumerate(open(args.input_file, 'r')):
        ggg += 1
        # Initial preprocessing, absolute paths has extra preprocessing
        line = preprocess(line, args.coreference)

        # Make sure char and word-level are in a similar representation now
        line = reverse_tokenize(tokenize_line(line))

        # Do some extra steps to fix some easy to fix problems
        line = do_extra_steps(line)

        # Restore coref indexing here
        # We first rewrite them to a format that convert() can handle,
        # final format is restored later
        if args.coreference == 'index':
            line = restore_coref_indexing(line, ref_dict)

        # Output of neural models can have non-finished edges, remove
        line = remove_dangling_edges(line)

        # Extra step to make sure digits are not added to arguments
        line = add_space_when_digit(line)

        # Restore variables here, also fix problems afterwards if there are any
        line = convert(line)

        # The digit problem might reoccur again here
        line = add_space_when_digit(line)

        # We did some hacky rewrites to make sure convert() didn't mess anything up
        # restore them in this step (polarity +, polite, etc)
        line = restore_rewrites(line)

        # Finally restore the coreference
        if args.coreference == 'index':
             # Replace the 'coref-' nodes with the reference
            line = add_coref(line)
        elif args.coreference == 'abs':
            # Replace absolute paths with reference here
            line = replace_absolute_paths(line, ref_dict)

        # Save the final line
        restored_lines.append(" ".join(line.strip().split()))

    # Print detailed results for the coreference methods
    if args.print_stats:
        print_coref_stats(args.coreference, replace_types, index_dict)

    # Write final output to file
    write_to_file(restored_lines, args.output_file)
