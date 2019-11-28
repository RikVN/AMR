#!/usr/bin/env python
# -*- coding: utf8 -*-

'''Script that tests given seq2seq model on given test data, also restoring and wikifying the produced AMRs

Input should either be a produced AMR -file or a folder to traverse. Outputs .restore, .pruned, .coref and .all files'''


import sys
import re
import argparse
import os
from multiprocessing import Pool
from amr_utils import get_default_amr, valid_amr
import wikify_file


def create_arg_parser():
    ''' If using -fol, -f and -s are directories. In that case the filenames of the sentence file and output file should match (except extension)
        If not using -fol, -f and -s are directories'''
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--input_file', required=True, help="File or folder to be post-processed")
    parser.add_argument('-s', '--sentence_file', default='', help="Sentence file or folder, only necessary for Wikification")
    parser.add_argument('-fol', '--folder', action='store_true', help="Whether -f is a folder")
    parser.add_argument('-se', '--sent_ext', default='.sent', help="Sentence extension - only necessary when doing folder (default .sent)")
    parser.add_argument('-o', '--out_ext', default='.seq.amr', help="Output extension - only necessary when doing folder (default .seq.amr)")
    parser.add_argument('-t', '--threads', default=16, type=int, help="Maximum number of parallel threads")
    parser.add_argument('-c', '--coreference', default='dupl', choices=['dupl', 'index', 'abs'], help='How to handle coreference - input was either duplicated/indexed/absolute path (default dupl)')
    parser.add_argument('-n', '--no_wiki', action='store_true', help='Not doing Wikification, since it takes a long time sometimes we want to skip it')
    parser.add_argument('-fo', '--force', action='store_true', help='For reprocessing of file even if file already exists')
    args = parser.parse_args()
    return args


def check_valid(restore_file, rewrite):
    '''Checks whether the AMRS in a file are valid, possibly rewrites to default AMR'''
    idx = 0
    warnings = 0
    all_amrs = []

    # For each AMR, check if it is valid, and write default when invalid
    for line in open(restore_file, 'r'):
        idx += 1
        if not valid_amr(line):
            print(('Error or warning in line {0}, write default\n'.format(idx)))
            warnings += 1
            default_amr = get_default_amr()
            all_amrs.append(default_amr)        ## add default when error
        else:
            all_amrs.append(line)

    # Write new AMRs to file if there are warnings
    print(('There are {0} AMRs with error'.format(warnings)))
    if rewrite and warnings > 0:
        with open(restore_file, 'w') as out_f:
            for line in all_amrs:
                out_f.write(line.strip() + '\n')
        out_f.close()


def add_wikification(in_file, sent_file, force):
    '''Function that adds wiki-links to produced AMRs'''
    wiki_file = in_file + '.wiki'

    # Check if wiki file doesn't exist already, if exists, skip
    if not os.path.isfile(wiki_file) or force:
        # Do wikification here
        wikify_file.wikify_file(in_file, sent_file)
        # Sanity check
        if len([x for x in open(sent_file, 'r')]) != len([x for x in open(wiki_file, 'r')]):
            print('Wikification failed for some reason (different lengths)\n\tSave file as backup with failed_wiki extension, no validating\n')
            os.system('mv {0} {1}'.format(wiki_file, wiki_file.replace('.wiki', '.failed_wiki')))
            return wiki_file, False
        else:
            check_valid(wiki_file, True)
            return wiki_file, True
    else:
        return wiki_file, True


def add_coreference(in_file, ext, force):
    '''Function that adds coreference back for each concept that occurs more than once
       Only works for -c dupl'''
    coref_file = in_file + ext

    # Only do if file doesn't exist yet
    if not os.path.isfile(coref_file) or force:
        os.system('python3 restore_duplicate_coref.py -f {0} --output_ext {1}'.format(in_file, ext))
    return coref_file


def do_pruning(in_file, force):
    '''Function that prunes duplicate output'''
    prune_file = in_file + '.pruned'

    # Only prune if output file doesn't already exist
    if not os.path.isfile(prune_file) or force:
        # Do pruning here
        os.system('python3 prune_amrs.py -f {0}'.format(in_file))
        # Check if they're still all valid
        check_valid(prune_file, True)
    return prune_file


def restore_amr(in_file, out_file, coref_type, force):
    '''Function that restores variables in output AMR
       Also restores coreference for index/absolute paths methods'''
    if not os.path.isfile(out_file) or force:
        restore_call = 'python3 restoreAMR/restore_amr.py -f {0} -o {1} -c {2}'.format(in_file, out_file, coref_type)
        os.system(restore_call)
        check_valid(out_file, True)
    return out_file


def process_file(input_list):
    '''Postproces AMR file'''
    # Unpack arguments
    input_file, sent_file, no_wiki, coreference, force = input_list

    # Sanity check first
    if (not os.path.isfile(sent_file) and not no_wiki) or not os.path.isfile(input_file) or not os.path.getsize(input_file):
        raise ValueError('Something is wrong, sent-file or amr-file does not exist or has no content')

    # Restore AMR first (variables)
    restore_file = input_file + '.restore'
    restore_file = restore_amr(input_file, restore_file, coreference, force)

    # Then do all postprocessing steps separately so we can see the individual impact of them
    # We always do pruning
    prune_file = do_pruning(restore_file, force)

    # Coreference restoring we only do for duplicating
    if coreference == 'dupl':
        _ = add_coreference(restore_file, '.coref', force)

    # We don't always want to do Wikification because it takes time
    if not no_wiki:
        _, success = add_wikification(restore_file, sent_file, force)

    # To get the final output file, we add all postprocessing steps together as well
    # We can already start from the prune file
    # Start with Wikification (if we want)
    if not no_wiki:
        next_file, success = add_wikification(prune_file, sent_file, force)
    else:
        next_file = prune_file
        success = True

    # Only continue if Wikification worked (or we skipped it)
    if success:
        # Then only do coreference for the duplicated coreference
        if coreference == 'dupl':
            final_file = add_coreference(next_file, '.coref.all', force)
        else:
            final_file = next_file

        # Write the final file to file that's always called the same
        os.system("cp {0} {1}.final".format(final_file, restore_file))
    else:
        raise ValueError('Wikification failed, consider using --no_wiki')


def match_files_by_name(amr_files, sent_files, no_wiki, coreference, force):
    '''Input is a list of both amr and sentence files, return matching pairs to test in parallel in the main function'''
    matches = []
    for amr in amr_files:
        # Return filename when given file /home/user/folder/folder2/filename.txt
        match_amr = amr.split('/')[-1].split('.')[0]
        for sent in sent_files:
            match_sent = sent.split('/')[-1].split('.')[0]
            # Matching sentence and AMR file, we can process those, so save them
            if match_sent == match_amr:
                matches.append([amr, sent, no_wiki, coreference, force])
                break
    return matches


def get_files(folder, ext):
    keep_files = []
    for root, _, files in os.walk(folder):
        for f in files:
            if f.endswith(ext) and '.char' not in f:
                keep_files.append(os.path.join(root, f))
    return sorted(keep_files)


if __name__ == "__main__":
    args = create_arg_parser()
    if not args.folder:
        print('Process single file\n')
        process_file([args.input_file, args.sentence_file, args.no_wiki, args.coreference, args.force])
    else:
        # Get AMR and sent files and match them
        sent_files = get_files(args.sentence_file, args.sent_ext)
        amr_files = get_files(args.input_file, args.out_ext)
        matching_files = match_files_by_name(amr_files, sent_files, args.no_wiki, args.coreference, args.force)
        print(('Processing {0} files, doing max {1} in parallel'.format(len(matching_files), args.threads)))
        pool = Pool(processes=args.threads)
        pool.map(process_file, matching_files)



