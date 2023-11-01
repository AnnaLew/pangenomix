### pangenomix
Tools for pangenome construction, analysis, and comparison. Derived from amr_pangenome, working towards Python2+3 compatibility.

# Building pangenome

### Conda setup

Before creating or activating the conda environment always run the following:

```bash
export PATH="${VSC_DATA}/miniconda3/bin:${PATH}" 
```

### Activate the conda environment

```bash
conda activate ./integrated-project-env/ 
```

### Install cd-hit with bioconda

```bash
conda install -c bioconda cd-hit
```

### Go to pangenomix/pangenomix directory

```bash
cd pangenomix/pangenomix
```

## CDS pangenome

### Start a python session

```bash
python
```
You might have to type python3 instead of python

### Import necessary modules

```python
import pangenome_analysis
import pangenome
from pangenome import list_faa_files
from pangenome import build_cds_pangenome
```

### Create lists of faa files 

```python
faa_files_50 = list_faa_files("/path/to/50faa/genomes")
faa_files_400 = list_faa_files("/path/to/400faa/genomes")
```
### Create output paths in the desired folder

The easiest way to copy their paths directly via VSC:

<img width="397" alt="image" src="https://github.com/AnnaLew/pangenomix/assets/57362758/72fb102b-bacc-4620-b711-0e7b96fef652">

### Build the pangenome

Make sure to change all the names with each run!

```python
build_cds_pangenome(genome_faa_paths=faa_files, output_dir="path/to/cd-hit-output", name="name_of_output")
```

Example

```python
build_cds_pangenome(genome_faa_paths=faa_files_50, output_dir="path/to/cd-hit-output/50_bactero_cdhit", name="50bactero")
```

## Non-coding pangenome

### Start a python session

```bash
python
```
You might have to type python3 instead of python

### Import necessary modules

```python
import pangenome_analysis
import pangenome
import manage_extensions
from pangenome import find_matching_genome_files, build_noncoding_pangenome
from manage_extensions import change_url_extensions, rename_files_with_extension
```

### Generate a list of URLs with .PATRIC.gff extensions

They will be generated in the same location as the input file, so don't specify the full output path.

```python
change_url_extensions("/path/to/file_faa.txt","new_file_gff.txt",".faa",".gff")
```

### Download the gff files

This is done in bash, not in python. I suggest opening a separate terminal to run this step, so your Python session is not lost, otherwise you will need to import all modules again. 

```bash
while read line; do wget -qN $(echo $line| tr -d '\"') -P ./path/to/output_gff ; done < path/to/input/new_file_gff.txt
```

### Change the .PATRIC.gff extension to .gff

```python
rename_files_with_extension("path/to/output_gff",".PATRIC.gff",".gff")
```

### Create a list of 2-tuples (genome_gff, genome_fna) and save them in an object. 

```python
matching_files=find_matching_genome_files("path/to/.gff", "path/to/.fna")
```

### Build the non-coding pangenome

Have in mind that some of the output will be created in the directory with .gff files. Precisely, a new "derived" folder will be created there. But all the other output will be in the directory specified by you. 

```python
build_noncoding_pangenome(genome_data=matching_files, output_dir="path/to/cd-hit-output/non-coding",name="name_of_output")
```

Example:

Notice that here I had to create the exact output directory, no new folders will be created, so make sure to create them by yourself, otherwise it will get messy. 

```python
build_noncoding_pangenome(genome_data=matching_files, output_dir="/path/to/cd-hit-output/non-coding/50_bactero_noncoding", name="50bactero")
```








