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
import pangenome_analysis, pangenome; from pangenome import list_faa_files, build_cds_pangenome
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
import pangenome_analysis, pangenome, manage_extensions; from pangenome import find_matching_genome_files, build_noncoding_pangenome; from manage_extensions import change_url_extensions, rename_files_with_extension
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

# Fit Heaps Law

### Start a python session

```bash
python
```
You might have to type python3 instead of python

### Import necessary modules

```python
import pangenome_analysis, sparse_utils; from pangenome_analysis import estimate_pan_core_size; from pangenome_analysis import fit_heaps_by_iteration
```

### Read the gene.npz file

```python
df_genes = sparse_utils.read_lsdf("path/to/gene.npz")
```

### Create df_pan_core 

df_pan_core is a DataFrame with pangenome + core genome size curve estimates as columns, iterations as index.

Side note: we can experiment with different numbers here, the number stands for the number of randomizations. 

```python
df_pan_core=estimate_pan_core_size(df_genes, 1)
```

### Fit Heaps Law to each iteration

```python
fit_heaps = fit_heaps_by_iteration(df_pan_core)
```

# EggNOG-maper

## Prepare input fasta file

### Start a python session

```bash
python
```
You might have to type python3 instead of python

### Import necessary modules

```python
import allele_identification; from allele_identification import create_alleles_fasta 
```

### Define all input files

Make sure to specify the directory for the output file, sorry for this, it is just the first version, so it's not perfect. 

```python
allele_npz_file = "path/to/allele.npz" 

gene_npz_label_file = "path/to/gene.npz.labels.txt" 

allele_npz_label_file = "path/to/allele.npz.labels.txt" 

input_faa = "path/to/nr.faa" 

output_faa = "path/to/_highly_expressed.faa " 
```

### Create the fasta file

```python
create_alleles_fasta(allele_npz_file, gene_npz_label_file, allele_npz_label_file, input_faa, output_faa) 
```

## Run the EggNog-mapper online tool

Follow the graphical instructions below.

![image](https://github.com/AnnaLew/pangenomix/assets/57362758/bfeca0ea-0f68-4351-bb7f-2146e5e651b0)

![image](https://github.com/AnnaLew/pangenomix/assets/57362758/81dbe9f5-653b-46a8-975d-95d87db0261d)

![image](https://github.com/AnnaLew/pangenomix/assets/57362758/9c0d72c8-9388-4149-a2cb-921ad4d7b094)

After the job finishes running, download the csv and excel files.

![image](https://github.com/AnnaLew/pangenomix/assets/57362758/3e897ab9-a597-4a9c-8692-aabd2dee60d7)





