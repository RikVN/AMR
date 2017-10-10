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
* Doing Smatch in parallel and printing nice,ordered output to screen
* Save parallel Smatch results in dictionary

## Getting Started

Simply clone the repository to your system to get started. All python programs are in Python 2.7, not 3.

### Prerequisites

The Wikification script needs [BeautifulSoup](https://pypi.python.org/pypi/beautifulsoup4), bs4, requests and lxml to work. All can be installed using pip.

## Running the scripts

There are two main components of this repository: pre-processing the input and post-processing the output.

### Pre-processing

There are 4 different scripts to change the usual AMR format to single-line format without variables and Wiki-links. The default one is var_free_amrs.py and handles coreference by duplicating the co-referring nodes.

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

By using the option -double, both the best aligned and original AMR are added in the dataset.

It is also possible to put the files in character-level format. There are options to keep POS-tags (-pos) or relations (-s) (:ARG1, :mod, etc) as single characters. If you used the Absolute Paths or Indexing method in a previous step, please indicate this by using -c.

```
python char_level_AMR.py -f sample_alignment_input/sample.tf
```

### Post-processing

The post-processing script are used to restore the variables and wiki-links, while also possibly handling the coreference nodes. There are individual scripts that can do each step, but they are combined in postprocess_AMRs.py. 

This script first restores the variables, by using a modified restoring script from [Didzis Gosko](https://github.com/didzis/tensorflowAMR/tree/master/SemEval2016/restoreAMR). Then, duplicate nodes are pruned (common problem when parsing) and coreference is put back (when duplicating that is, for Abs and Index method this is done in the restoring step). 

Finally, Wikipedia links are restored using Spotlight. These steps are done separately (creating .restore, .prune, .coref and .wiki files), but also together (creating .all file).

```
python postprocess_AMRs.py -f sample_alignment_input/sample.char.tf -s sample_alignment_input/sample.sent
```

Here -f is the file to be processed and -s is the sentence file (needed for Wikification) It is possible to use -no_wiki to skip the Wikification step. These options can also be used to process a whole folder (use -fol) in parallel, to speed up the process. Check the script for details.

### Evaluation

The script **evaluate_AMRs.py** is specifically made to do the (Smatch) evaluation in parallel for multiple epochs, files and types of post-processing. It prints nice, ordered output to the screen.

For example, if you have results of the 2 last epochs, for 4 different files and for output extensions .restore, .coref and .wiki, the output looks like this (numbers made up):

```
                       file1  file2  file3  file4
19 epochs (.restore)   0.54   0.52   0.44   0.61
19 epochs (.coref)     0.57   0.55   0.47   0.63
19 epochs (.wiki)      0.55   0.51   0.48   0.62   
20 epochs (.restore)   0.59   0.58   0.45   0.62
20 epochs (.coref)     0.62   0.59   0.49   0.65
20 epochs (.wiki)      0.60   0.61   0.50   0.66
```

Note that the epoch number must be recognizable in either the file or folder name, by using e.g. epoch19 or ep19. Also, output files and sentences files are matched base on their identifier before the extension and after a dash, e.g. files should look like ```/home/user/folder/experiment/epoch12/dataset-identifier.seq.amr.restore```. What will be extracted are **12** and **identifier**.

It is possible to only see a certain output type (e.g. restore, coref, wiki) by using the ```-type``` argument. Results are saved in a dictionary that is read again on next use as to not process the same file twice. 

Usage:

```
python evaluate_AMRs.py -g [gold_folder] -p [output_folder] -type wiki -res_dict [res_dict_file]
```


## Important ##

* All scripts are AMR-specific, meaning that they are very reliant on the gold standard AMR formatting.
* This is **only** for pre- and post-processing, **not training and testing!** I recommend [OpenNMT](http://opennmt.net/) as a library for doing the actual experiments. All parameter settings can be found in the papers described below.
* Please see all individual scripts for all parameter options and samples of the input and output.

## Silver data ##

The silver data that I used in the experiments for the CLIN paper can be downloaded [here](http://www.let.rug.nl/rikvannoord/AMR/silver_data/). The silver data was obtained by parsing all sentences in the [Groningen Meaning Bank](http://gmb.let.rug.nl/) with the parsers [CAMR](https://github.com/c-amr/camr) and [JAMR](https://github.com/jflanigan/jamr). The data folder contains seven files: all CAMR and JAMR parses (1.25 million, aligned with each other) and sets of AMRs (20k, 50k, 75k, 100k, 500k) that were used in our experiments (CAMR only). For more details please see our [CLIN paper](https://arxiv.org/pdf/1705.09980.pdf).

Note that since the Groningen Meaning Bank is public domain, you can freely use these silver data sets in your own experiments. If you do, please cite our [CLIN paper](https://arxiv.org/pdf/1705.09980.pdf) and the [GMB paper](http://www.lrec-conf.org/proceedings/lrec2012/pdf/534_Paper.pdf).

## Papers ##

Please see the following papers for details. For general AMR parsing methods:

* *Neural Semantic Parsing by Character-based Translation: Experiments with Abstract Meaning Representations*, Rik van Noord & Johan Bos, Accepted in CLiN 2017 Journal. [[PDF]](https://arxiv.org/pdf/1705.09980.pdf)

For coreference-specific information:

* *Dealing with Co-reference in Neural Semantic Parsing*, Rik van Noord & Johan Bos, To appear in IWCS Workshop SemDeep-2, Montpellier, 2017.

## About the Author

**Rik van Noord**, PhD student at University of Groningen, supervised by Johan Bos. Please see my [personal website](http://rikvannoord.nl/) for more information. I'm happy to answer questions.
