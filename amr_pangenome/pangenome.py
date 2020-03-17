#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 12 10:18:29 2020

@author: jhyun95

Pan-genome construction tools including consolidating redundant sequences,
gene sequence cluster identification by CD-Hit, and constructing gene/allele tables.
"""

import os
import subprocess as sp
import hashlib 

import pandas as pd

def build_cds_pangenome(genome_faa_paths, output_dir, name='Test', 
                        cdhit_args={'-n':5, '-c':0.8}, fastasort_path=None):
    ''' 
    TODO
    '''
    
    ''' Merge FAAs into one file with non-redundant sequences '''
    print 'Identifying non-redundant CDS sequences...'
    output_nr_faa = output_dir + '/' + name + '_nr.faa' # final non-redundant FAA files
    output_shared_headers = output_dir + '/' + name + '_redundant_headers.tsv' # records headers that have the same sequence
    output_nr_faa = output_nr_faa.replace('//','/')
    output_shared_headers = output_shared_headers.replace('//','/')
    non_redundant_seq_hashes = consolidate_cds(genome_faa_paths, output_nr_faa, output_shared_headers)
    # maps sequence hash to headers of that sequence, in order observed
    
    ''' Apply CD-Hit to non-redundant CDS sequences '''
    output_nr_faa_copy = output_nr_faa + '.cdhit' # temporary FAA copy generated by CD-Hit
    output_nr_clstr = output_nr_faa + '.cdhit.clstr' # cluster file generated by CD-Hit
    cluster_cds(output_nr_faa, output_nr_faa_copy, cdhit_args)
    os.remove(output_nr_faa_copy) # delete CD-hit copied sequences
    
    ''' Extract genes and alleles, rename unique sequences as <name>_C#A# '''
    output_allele_names = output_dir + '/' + name + '_allele_names.tsv' # allele names vs non-redundant headers
    output_allele_names = output_allele_names.replace('//','/')
    header_to_allele = rename_genes_and_alleles(output_nr_clstr, output_nr_faa, output_nr_faa, 
                                                output_allele_names, name=name,
                                                fastasort_path=fastasort_path)
    # maps representative non-redundant headers to short names <name>_C#A#
    
    ''' Process gene/allele membership into binary tables '''
    output_allele_table = output_dir + '/' + name + '_strain_by_allele.csv.gz'
    output_gene_table = output_dir + '/' + name + '_strain_by_gene.csv.gz'
    output_allele_table = output_allele_table.replace('//','/')
    output_gene_table = output_gene_table.replace('//','/')
    df_alleles, df_genes = build_genetic_feature_tables(output_nr_clstr, genome_faa_paths, 
                              output_shared_headers, output_allele_table, output_gene_table, 
                              header_to_allele=header_to_allele)
    return df_alleles, df_genes
    

def consolidate_cds(genome_faa_paths, nr_faa_out, shared_headers_out):
    ''' 
    Combines CDS protein sequences for many genomes into a single file while
    without duplicate sequences to be clustered using cluster_cds (CD-Hit wrapper),
    and tracks headers that share the same sequence.
    
    Parameters
    ----------
    genome_faa_paths : list
        Paths to genome FAA files to combine
    nr_faa_out : str
        Output path for combined non-redundant FAA file
    shared_headers_out : str
        Output path for shared headers TSV file

    Returns
    -------
    non_redundant_seq_hashes : dict
        Maps non-redundant sequence hashes to a list of headers, in order observed
    '''
    non_redundant_seq_hashes = {} # maps sequence hash to headers of that sequence, in order observed
    encounter_order = [] # stores sequence hashes in order encountered
    
    def process_header_and_seq(header, seq_blocks, output_file):
        ''' Processes a header/sequence pair against the running list of non-redundant sequences '''
        if len(header) > 0 and len(seq_blocks) > 0: # process previous sequence record
            seq = ''.join(seq_blocks)
            seqhash = hashlib.sha256(seq).hexdigest()
            if seqhash in non_redundant_seq_hashes: # record repeated appearances of sequence
                non_redundant_seq_hashes[seqhash].append(header)
            else: # first encounter of a sequence, record to non-redundant FAA file
                encounter_order.append(seqhash)
                non_redundant_seq_hashes[seqhash] = [header]
                output_file.write('>' + header + '\n')
                output_file.write('\n'.join(seq_blocks) + '\n')
    
    ''' Scan for redundant CDS for all FAA files, build non-redundant file '''
    with open(nr_faa_out, 'w+') as f_nr_out:
        for faa_path in genome_faa_paths:
            with open(faa_path, 'r') as f:
                header = ''; seq_blocks = []
                for line in f:
                    if line[0] == '>': # header encountered
                        process_header_and_seq(header, seq_blocks, f_nr_out)
                        header = __get_header_from_fasta_line__(line)
                        seq_blocks = []
                    else: # sequence line encountered
                        seq_blocks.append(line.strip())
                process_header_and_seq(header, seq_blocks, f_nr_out) # process last record
                
    ''' Save shared headers to file '''
    with open(shared_headers_out, 'w+') as f_header_out:
        for seqhash in encounter_order:
            headers = non_redundant_seq_hashes[seqhash]
            if len(headers) > 1:
                f_header_out.write('\t'.join(headers) + '\n')
    return non_redundant_seq_hashes
        
                
def cluster_cds(faa_file, cdhit_out, cdhit_args={'-n':5, '-c':0.8}):
    '''
    Runs CD-Hit on a FAA file (i.e. one generated by consolidate_cds).
    Requires cd-hit to be available in PATH.
    
    Parameters
    ----------
    faa_file : str
        Path to FAA file to be clustered, i.e. from consolidate_cds
    cdhit_out : str
        Path to be provided to CD-Hit output argument
    cdhit_args : dict
        Dictionary of alignment arguments to be provided to CD-Hit, other than
        -i, -o, and -d. (default {'-n':f, '-c':0.8})
    ''' 
    args = ['cd-hit', '-i', faa_file, '-o', cdhit_out, '-d', '0']
    for arg in cdhit_args:
        args += [arg, str(cdhit_args[arg])]
    print 'Running:', args
    for line in __stream_stdout__(' '.join(args)):
        print line

def rename_genes_and_alleles(clstr_file, nr_faa_file, nr_faa_out, feature_names_out, name='Test',
                            fastasort_path=None):
    '''
    Processes a CD-Hit CLSTR file (clstr_file) to rename headers in the orignal
    FAA (nr_faa_file) as <name>_C#A# based on cluster membership and stores header-name
    mappings as a TSV (feature_names_out).
    
    Can optionally sort final FAA file if fastasort_path is specified, from Exonerate
    https://www.ebi.ac.uk/about/vertebrate-genomics/software/exonerate
    
    Parameters
    ----------
    clstr_file : str
        Path to CLSTR file generated by CD-Hit
    nr_faa_file : str
        Path to FAA file corresponding to clstr_file
    nr_faa_out : str
        Output path for renamed FAA, will overwrite if equal to nr_faa
    feature_names_out : str
        Output path for header-allele name mapping TSV file
    name : str
        Header to append output files and allele names (default 'Test')
    fastasort_path : str
        Path to Exonerate fastasort, used to optionally sort nr_faa (default None)
        
    Returns
    -------
    header_to_allele : dict
        Maps original headers to new allele names
    '''
    
    ''' Read through CLSTR file to map original headers to C#A# names '''
    header_to_allele = {} # maps representative header to allele name (name_C#A#)
    max_cluster = 0 
    with open(feature_names_out, 'w+') as f_naming:
        with open(clstr_file, 'r') as f_clstr:
            for line in f_clstr:
                if line[0] == '>': # starting new gene cluster
                    cluster_num = line.split()[-1].strip() # cluster number as string
                    max_cluster = cluster_num
                else: # adding allele to cluster
                    data = line.split()
                    allele_num = data[0] # allele number as string
                    allele_header = data[2][1:-3] # old allele header
                    allele_name = name + '_C' + cluster_num + 'A' + allele_num # new short header
                    header_to_allele[allele_header] = allele_name
                    f_naming.write(allele_name + '\t' + allele_header + '\n')
                    
    ''' Create the FAA file with renamed features '''
    with open(nr_faa_file, 'r') as f_faa_old:
        with open(nr_faa_out + '.tmp', 'w+') as f_faa_new:
            ''' Iterate through alleles in cluster/allele order '''
            for line in f_faa_old:
                if line[0] == '>': # writing updated header line
                    allele_header = line[1:].strip()
                    allele_name = header_to_allele[allele_header]
                    f_faa_new.write('>' + allele_name + '\n')
                else: # writing sequence line
                    f_faa_new.write(line)
    
    ''' Move FAA file to desired output path '''
    if nr_faa_out == nr_faa_file: # if overwriting, remove old faa file
        os.remove(nr_faa_file) 
    os.rename(nr_faa_out + '.tmp', nr_faa_out)
    
    ''' If available, use exonerate.fastasort to sort entries in fasta file '''
    if fastasort_path:
        print 'Sorting sequences by header...'
        args = ['./' + fastasort_path, nr_faa_out]
        with open(nr_faa_out + '.tmp', 'w+') as f_sort:
            sp.call(args, stdout=f_sort)
        os.rename(nr_faa_out + '.tmp', nr_faa_out)
    return header_to_allele
    

def build_genetic_feature_tables(clstr_file, genome_faa_paths, shared_header_file, 
                                 allele_table_out, gene_table_out, header_to_allele=None):
    '''
    Builds two binary tables based on the presence/absence of genetic features, 
    allele x genome (allele_table_out) and gene x genome (gene_table_out). 
    Uses a CD-Hit CLSTR file, the corresponding original FAA files, and 
    shared header mappings.
    
    Parameters
    ----------
    clstr_file : str
        Path to CD-Hit CLSTR file used to build header-allele mappings
    genome_faa_paths : list
        Paths to genome FAA files originally combined as clustered (see consolidate_cds)
    shared_header_file : str
        Path to shared header TSV file (see conslidate_cds)
    allele_table_out : str
        Output path for binary allele x genome table, expect CSV or CSV.GZ (default None)
    gene_table_out : str
        Output path for binary gene x genome table, expect CSV or CSV.GZ (default None)
    header_to_allele : dict
        Pre-calculated header-allele mappings corresponding to clstr_file,
        if available from rename_genes_and_alleles (default None)

    Returns 
    -------
    df_alleles : pd.DataFrame
        Binary allele x genome table
    df_genes : pd.DataFrame
        Binary gene x genome table
    '''
    if header_to_allele is None: # header-allele mapping not provided, re-build from CLSTR
        header_to_allele = {} # maps representative header to allele name (name_C#A#)
        with open(clstr_file, 'r') as f_clstr:
            for line in f_clstr:
                if line[0] == '>': # starting new gene cluster
                    cluster_num = line.split()[-1].strip() # cluster number as string
                    max_cluster = cluster_num
                else: # adding allele to cluster
                    data = line.split()
                    allele_num = data[0] # allele number as string
                    allele_header = data[2][1:-3] # old allele header
                    allele_name = name + '_C' + cluster_num + 'A' + allele_num # new short header
                    header_to_allele[allele_header] = allele_name
    
    ''' Load headers that share the same sequence '''
    shared_header_to_allele = {} # same format as header_to_allele
    with open(shared_header_file, 'r') as f_header:
        for line in f_header:
            headers = [x.strip() for x in line.split('\t')]
            if len(headers) > 1:
                repr_header = headers[0]
                repr_allele = header_to_allele[repr_header]
                for alt_header in headers[1:]:
                    shared_header_to_allele[alt_header] = repr_allele
                    
    ''' Initialize gene and allele tables '''
    faa_to_genome = lambda x: x.split('/')[-1][:-4]
    genome_order = sorted([faa_to_genome(x) for x in genome_faa_paths]) # for genome names, trim .faa from filenames
    print 'Sorting alleles...'
    allele_order = sorted(header_to_allele.values()) 
    df_alleles = pd.DataFrame(index=allele_order, columns=genome_order)
    print 'Sorting genes...'
    gene_order = []; last_gene = None
    for allele in allele_order:
        gene = __get_gene_from_allele__(allele)
        # print allele, gene, last_gene
        if gene != last_gene:
            gene_order.append(gene)
            last_gene = gene
    df_genes = pd.DataFrame(index=gene_order, columns=genome_order)
    print 'Genomes:', len(genome_order)
    print 'Alleles:', len(allele_order)
    print 'Genes:', len(gene_order)
        
    ''' Scan original genome file for allele and gene membership '''
    for genome_faa in genome_faa_paths:
        genome = faa_to_genome(genome_faa)
        genome_alleles = []; genome_genes = []
        with open(genome_faa, 'r') as f_faa:
            for line in f_faa:
                ''' Load all alleles and genes per genome '''
                if line[0] == '>':
                    header = __get_header_from_fasta_line__(line)
                    allele = header_to_allele[header] if header in header_to_allele \
                        else shared_header_to_allele[header]
                    gene = __get_gene_from_allele__(allele)
                    genome_alleles.append(allele)
                    genome_genes.append(gene)
            ''' Save to running table  '''
            print 'Updating genome', genome, len(genome_alleles), len(genome_genes)
            df_alleles.loc[genome_alleles, genome] = 1
            df_genes.loc[genome_genes, genome] = 1
    
    if allele_table_out:
        df_alleles.to_csv(allele_table_out)
    if gene_table_out:
        df_genes.to_csv(gene_table_out)
    return df_alleles, df_genes


def __get_gene_from_allele__(allele):
    return 'A'.join(allele.split('A')[:-1])

def __get_header_from_fasta_line__(line):
    return line.split()[0][1:].strip()
            
def __stream_stdout__(command):
    ''' Hopefully Jupyter-safe method for streaming process stdout '''
    process = sp.Popen(command, stdout=sp.PIPE, shell=True)
    while True:
        line = process.stdout.readline()
        if not line:
            break
        yield line.rstrip()
    