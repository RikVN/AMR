#!/bin/bash
# Script that checks whether everything still works for preprocessing/postprocessing of AMR files
# for the AMR repository of https://github.com/RikVN/AMR
set -eu -o pipefail

# Set variables this scripts needs access to
cur_dir=$(pwd)
TEST_FILE="${cur_dir}/sample_input/sample.txt"
SENT_FILE="${TEST_FILE}.sent"
ALIGNED_ROOT="${cur_dir}/sample_alignment_input/sample"
ALIGNED_FILE="${ALIGNED_ROOT}.txt"

# We don't always want to run smatch (takes long for longer files)
do_smatch=true
SMATCH="${cur_dir}/smatch/smatch.py"
smatch_arguments="-r 5 --significant 3"


# Test the pruning process for word-level duplication (most to prune)
test_pruning(){
	printf "\n----------------------------------------------\n"
	printf "Testing the pruning script separately\n\n"
	python3 ${cur_dir}/var_free_amrs.py -f $TEST_FILE --keep_wiki
	python3 ${cur_dir}/restoreAMR/restore_amr.py -f ${TEST_FILE}.tf -o ${TEST_FILE}.out
	python3 ${cur_dir}/prune_amrs.py -f ${TEST_FILE}.out
	# Replace coreference for the nodes that are left
	python3 ${cur_dir}/restore_duplicate_coref.py -f ${TEST_FILE}.out.pruned --output_ext .coref
	# All AMRs should be valid, reformatting can check this
	python3 ${cur_dir}/reformat_single_amrs.py -f ${TEST_FILE}.out.pruned -e .form --valid
	python3 ${cur_dir}/reformat_single_amrs.py -f ${TEST_FILE}.out.pruned.coref -e .form --valid
	# Compare to original file for both created files
	if $do_smatch; then
		python3 $SMATCH -f ${TEST_FILE}.out.pruned.form $TEST_FILE $smatch_arguments
		python3 $SMATCH -f ${TEST_FILE}.out.pruned.coref.form $TEST_FILE $smatch_arguments
	fi	
}


# Test best AMR permutation
test_best_permutation(){
	printf "\n----------------------------------------------\n"
	printf "Testing the best permutation script (needs aligned input!)\n\n"
	python3 ${cur_dir}/best_amr_permutation.py -f $ALIGNED_FILE
	# Smatch should give equal score (or almost) as the one with duplication
	python3 ${cur_dir}/restoreAMR/restore_amr.py -f ${ALIGNED_ROOT}.tf.best -o ${ALIGNED_FILE}.out
	python3 ${cur_dir}/restore_duplicate_coref.py -f ${ALIGNED_FILE}.out --output_ext .coref
	python3 ${cur_dir}/reformat_single_amrs.py -f ${ALIGNED_FILE}.out.coref -e .form --valid
	if $do_smatch; then
		python3 $SMATCH -f ${ALIGNED_FILE}.out.coref.form $TEST_FILE $smatch_arguments
	fi
}


# Test Wikification with char-level input + restoring
test_wikification(){
	printf "\n----------------------------------------------\n"
	printf "Testing Wikification after restoring AMRs\n\n"
	python3 ${cur_dir}/var_free_amrs.py -f $TEST_FILE
	python3 ${cur_dir}/char_level_AMR.py -s -f ${TEST_FILE}.tf
	python3 ${cur_dir}/restoreAMR/restore_amr.py -f ${TEST_FILE}.tf -o ${TEST_FILE}.tf.restore -c dupl
	python3 ${cur_dir}/wikify_file.py -f ${TEST_FILE}.tf.restore -s ${TEST_FILE}.sent
}


# Test loop of removing variables and then restoring AMRs
test_restore(){
	for rep in char word; do
		for coref in dupl index abs; do
			printf "\n----------------------------------------------\n"
			printf "Testing $rep representation for coref $coref\n\n"
			coref_tagged="-c" #default, overwrite for dupl
			rep_ext=".tf" #default, overwrite for char models
			
			# Rewrite the AMRs to correct coreference format first
			if [[ $coref == "dupl" ]] ; then
				python3 ${cur_dir}/var_free_amrs.py -f $TEST_FILE --keep_wiki
				coref_tagged=""
			elif [[ $coref == "index" ]] ; then
				python3 ${cur_dir}/create_coref_indexing.py -f $TEST_FILE --keep_wiki
			elif [[ $coref == "abs" ]] ; then
				python3 ${cur_dir}/create_coref_paths.py -f $TEST_FILE -p $coref --keep_wiki
			fi
			
			# For char, put the input file in character-level format, with super characters
			if [[ $rep == "char" ]] ; then
				python3 ${cur_dir}/char_level_AMR.py -s $coref_tagged -f ${TEST_FILE}.tf
				rep_ext=".char.tf"
			fi
			
			# Restore the AMR with postprocessing
			# Don't do Wikification, takes long, plus not necessary if we use --keep_wiki
			# Sent-file can be empty for this part of the script
			python3 ${cur_dir}/postprocess_AMRs.py -f ${TEST_FILE}$rep_ext -s $SENT_FILE -c $coref --no_wiki --force
			
			# Restore to AMR-line format for the output files
			# For abs/indexing there is no .coref, restore file already has the coref
			if [[ $coref == 'dupl' ]] ; then
				python3 ${cur_dir}/reformat_single_amrs.py -f ${TEST_FILE}${rep_ext}.restore.coref -e .form --valid
			else
				python3 ${cur_dir}/reformat_single_amrs.py -f ${TEST_FILE}${rep_ext}.restore -e .coref.form --valid
			fi
			python3 ${cur_dir}/reformat_single_amrs.py -f ${TEST_FILE}${rep_ext}.restore.pruned -e .form --valid
			python3 ${cur_dir}/reformat_single_amrs.py -f ${TEST_FILE}${rep_ext}.restore.final -e .form --valid
			
			# Do smatch if wanted to check that scores are not super low
			if $do_smatch; then
				printf "\n\nSmatch score for coref file\n\n"
				python3 $SMATCH -f ${TEST_FILE}${rep_ext}.restore.coref.form $TEST_FILE $smatch_arguments
				printf "\n\nSmatch score for final file\n\n"
				python3 $SMATCH -f ${TEST_FILE}${rep_ext}.restore.final.form $TEST_FILE $smatch_arguments
			fi
		done
	done
}	

# Run tests here
test_restore
test_pruning
test_best_permutation
test_wikification
