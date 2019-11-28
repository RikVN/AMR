# Pre- and post-processing scripts for neural sequence-to-sequence AMR parsing

This repository contains a list of scripts that help in pre- and post-processing for neural AMR parsing. It helps put the AMR files into structures sequence-to-sequence models can handle. 

The scripts can do the following things:

* Convert AMRs to single-line format and split AMRs and sentences
* Remove variables and wiki-links
* Handle co-referring nodes in different ways
* Swap AMR branches so that the surface string best matches the word order
* Put the input files in different character-level formats
* Restore variables and Wiki-links in the output
* Restore the co-referring nodes
* Remove duplicate output

## Getting Started

Simply clone the repository to your system to get started. All python programs are in **Python 3**. Also put Smatch in this folder.

```
git clone https://github.com/RikVN/AMR
cd AMR
git clone https://github.com/snowblink14/smatch
```

### Prerequisites

All requirements can be installed using pip:

```
pip install -r requirements.txt
```

## Running the scripts

There are two main components of this repository: pre-processing the input and post-processing the output.

I will explain everything in more detail below, but if you want to test if everything works, please run:

```
./test_pipeline.sh
```

This assumes that smatch is present in the main AMR folder.

### Pre-processing

There are 4 different scripts to change the usual AMR format to single-line format without variables and Wiki-links. The default one is ``var_free_amrs.py`` and handles coreference by duplicating the co-referring nodes.

```
python var_free_amrs.py -f sample_input/sample.txt
```

There are two scripts that handle co-reference, either by using the Absolute Paths method or the Indexing method.

```
python create_coref_paths.py -f sample_input/sample.txt -p abs
python create_coref_indexing.py -f sample_input/sample.txt
```

The last script is similar to var_free_amrs.py, but swaps different AMR branches to best match the word order of the sentence. 

**This script needs the aligned AMRs as input!**

```
python best_amr_permutation.py -f sample_alignment_input/sample.txt
```

By using the option --double, both the best aligned and original AMR are added to the dataset.

It is also possible to put the files in character-level format. There are options to keep POS-tags (-p) or relations (-s) (:ARG1, :mod, etc) as single characters. If you used the Absolute Paths or Indexing method in a previous step, please indicate this by using -c.

```
python char_level_AMR.py -f sample_alignment_input/sample.txt.tf
```

### Post-processing

The post-processing script are used to restore the variables and wiki-links, while also possibly handling the coreference nodes. There are individual scripts that can do each step, but they are combined in ``postprocess_AMRs.py``. 

This script first restores the variables, by using a modified restoring script from [Didzis Gosko](https://github.com/didzis/tensorflowAMR/tree/master/SemEval2016/restoreAMR). Then, duplicate nodes are pruned (common problem when parsing) and coreference is put back (when duplicating that is, for Abs and Index method this is done in the restoring step). 

Finally, Wikipedia links are restored using Spotlight. These steps are done separately (creating .restore, .prune, .coref and .wiki files), but also together (creating .final file).

```
python postprocess_AMRs.py -f sample_alignment_input/sample.txt.char.tf -s sample_alignment_input/sample.sent
```

Here -f is the file to be processed and -s is the sentence file (needed for Wikification) It is possible to use --no_wiki to skip the Wikification step. These options can also be used to process a whole folder (use -fol) in parallel, to speed up the process. Check the script for details.

The AMRs will in one-line format, i.e. one AMR per line. If you want the more readable AMR format back, run this:

``
python reformat_single_amrs.py -f sample_input/sample.txt.char.tf.restore.final -e .form
``


## Silver data ##

The silver data that I used in the experiments for the CLIN paper can be downloaded [here](http://www.let.rug.nl/rikvannoord/AMR/silver_data/). The silver data was obtained by parsing all sentences in the [Groningen Meaning Bank](http://gmb.let.rug.nl/) with the parsers [CAMR](https://github.com/c-amr/camr) and [JAMR](https://github.com/jflanigan/jamr). The data folder contains seven files: all CAMR and JAMR parses (1.25 million, aligned with each other) and sets of AMRs (20k, 50k, 75k, 100k, 500k) that were used in our experiments (CAMR only). For more details please see our [CLIN paper](https://clinjournal.org/clinj/article/view/72/64).

Note that since the Groningen Meaning Bank is public domain, you can freely use these silver data sets in your own experiments. If you do, please cite our [CLIN paper](https://clinjournal.org/clinj/article/view/72/64) and the [GMB paper](http://www.lrec-conf.org/proceedings/lrec2012/pdf/534_Paper.pdf).

## Running my best model ##

I made the best model in the CLIN paper publicly available [here](http://www.let.rug.nl/rikvannoord/AMR/best_model/). If you download it and have [OpenNMT](http://opennmt.net/) installed, you should be able to run it. Note that the input (SOURCE_FILE) must be POS-tagged and in character-level format. I also made my vocabulary files available, make sure you arrive at (more or less) the same vocabulary for your input! You can run it like this:

```
th translate.lua -src $SOURCE_FILE -output $OUTPUT_FILE -model $MODEL_FILE -beam_size 5 -max_sent_length 500 -replace_unk -n_best 1 -gpuid 1 -log_file $LOG_FILE -fallback_to_cpu
```

The output can be post-processed applying the scripts described above. If there are any issues, please let me know!

## Papers ##

Please see the following papers for details. For general AMR parsing methods:

* *Neural Semantic Parsing by Character-based Translation: Experiments with Abstract Meaning Representations*, Rik van Noord & Johan Bos, CLiN 2017 Journal. [[PDF]](https://clinjournal.org/clinj/article/view/72/64)

For coreference-specific information:

* *Dealing with Co-reference in Neural Semantic Parsing*, Rik van Noord & Johan Bos, Proceedings of the 2nd Workshop on Semantic Deep Learning (SemDeep-2), Montpellier, 2017. [[PDF]](http://aclweb.org/anthology/W/W17/W17-7306.pdf)

## About the Author

**Rik van Noord**, PhD student at University of Groningen, supervised by Johan Bos. Please see my [personal website](http://rikvannoord.nl/) for more information. I'm happy to answer questions.
