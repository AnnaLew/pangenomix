### pangenomix
Tools for pangenome construction, analysis, and comparison. Derived from amr_pangenome, working towards Python2+3 compatibility.

# Building pangenome

### Conda setup

Before creating or activating the conda environment always run the following:

```bash
export PATH="${VSC_DATA}/miniconda3/bin:${PATH}" 
```

### Activate the conda environment

You might have to include the full path to the environment. 

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

# Fit Heaps Law and plot the pangenome

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
Iterations are set to 100 here.

Side note: we can experiment with different numbers here, the number stands for the number of randomizations. 

```python
df_pan_core=estimate_pan_core_size(df_genes, 100)
```

### Calculate the Mean of 100 iterations and plot
Do this immediately after iterations as each time a new run will give different results.
```python
import plot; from plot import calculate_mean
Mean = calculate_mean(df_pan_core, jpgName)
```

### Fit Heaps Law to the mean value of iteration

```python
fit_heaps = fit_heaps_by_iteration(Mean)
```

### Export the result to csv
Save the result of heaps law!
Do this if you want to have the results as csv format.
```python
df_pan_core.to_csv("path/to/.csv")
fit_heaps.to_csv("path/to/.csv")
```

# Compute Core genes

### Start a python session

```bash
python
```
You might have to type python3 instead of python

### Import necessary modules

```python
import pangenome_analysis, sparse_utils; from pangenome_analysis import compute_bernoulli_grid_core_genome; from sparse_utils import LightSparseDataFrame
```
### Read npz file and convert it

```python
df_genes = sparse_utils.read_lsdf("path/to/gene.npz")
df_genes_dense = LightSparseDataFrame.to_sparse_arrays(df_genes)
```
### Compute the core genome

```python
compute_core_genome = compute_bernoulli_grid_core_genome(df_genes_dense,prob_bounds=(0.8,0.99999999), init_capture_prob=0.9999,init_gene_freqs=None)
```

# EggNOG-maper

## Prepare input fasta file

### Important note

You might run into issues if you don't have some libraries installed, so you might want to pip install them beforehand. 

```bash
pip install numpy
pip install pandas
pip install Bio
pip install ast
```

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

# Core and accessory genome 

This code will allow you to extract the core and accessory pangenomes 

### Important note

You might run into issues if you don't have some libraries installed, so you might want to pip install them beforehand. 

```bash
pip install numpy
pip install pandas
pip install Bio
pip install ast
```

### Start a python session

```bash
python
```
You might have to type python3 instead of python

### Import necessary modules

```python
import core_genome; from core_genome import create_core_genes_fasta 
```

### Define all input files

Make sure to specify the directory for the output file, sorry for this, it is just the first version, so it's not perfect. 

```python
allele_npz_file = "path/to/allele.npz" 

allele_npz_label_file = "path/to/allele.npz.labels.txt"

gene_npz_file = "path/to/gene.npz"

gene_npz_label_file = "path/to/gene.npz.labels.txt"

input_faa = "path/to/nr.faa"

genomes_num = number_of_your_genomes

output_faa = "path/to/_core.faa " 
```

### Very important note

genomes_num variable allows you to decide what in which percentage of genomes you want your genomes to be found. E.g. if you consider core genes the genes present in all the genomes, then set it to 400 in case you have 400 genomes and to 50 in case you have 50 genomes. In our case I want you to run it for the numbers/percentages below.

For 50 genome set:

* 100% - 50
* 98% - 49
* 96% - 48 
* 94% - 47
* 16% - 8

For 400 genome set:

* 100% - 400
* 99% - 396
* 98% - 392
* 96% - 384
* 95% - 380
* 94% - 376
* 16% - 64
* 15% - 60

Also, have in mind that you need to change the name of output file each time, so that you keep track of the percentages.


### Create the fasta file

```python
create_core_genes_fasta(allele_npz_file, allele_npz_label_file, gene_npz_file, gene_npz_label_file, input_faa, genomes_num, output_faa)
```

### Count the number of genes in each fasta file

To count the number of genes in each fasta file, you need to go to the location of the fasta file and then use the following command:

```bash
grep -c "^>" file_core.faa
```


