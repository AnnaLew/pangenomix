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
import numpy as np

def build_cds_pangenome(genome_faa_paths, output_dir, name='Test', 
                        cdhit_args={'-n':5, '-c':0.8}, fastasort_path=None):
    ''' 
    Constructs a pan-genome based on protein sequences with the following steps:
    1) Merge FAA files for genomes of interest into a non-redundant list
    2) Cluster CDS by sequence into putative genes using CD-Hit
    3) Rename non-redundant CDS as <name>_C#A#, referring to cluster and allele number
    4) Compile allele/gene membership into binary allele x genome and gene x genome tables
    
    Generates six files within output_dir:
    1) <name>_strain_by_allele.csv.gz, binary allele x genome table
    2) <name>_strain_by_gene.csv.gz, binary gene x genome table
    3) <name>_nr.faa, all non-redundant CDSs observed, with headers <name>_C#A#
    4) <name>_nr.faa.cdhit.clstr, CD-Hit output file from clustering
    5) <name>_allele_names.tsv, mapping between <name>_C#A# to original CDS headers
    6) <name>_redundant_headers.tsv, lists of headers sharing the same CDS, with the
        representative header relevant to #5 listed first for each group.
    7) <name>_missing_headers.txt, lists headers for original entries missing sequences
    
    Parameters
    ----------
    genome_faa_paths : list 
        FAA files containing CDSs for genomes of interest. Genome 
        names are inferred from these FAA file paths.
    output_dir : str
        Path to directory to generate outputs and intermediates.
    name : str
        Header to prepend to all output files and allele names (default 'Test')
    cdhit_args : dict
        Alignment arguments to pass CD-Hit, other than -i, -o, and -d
        (default {'-n':5, '-c':0.8})
    fastasort_path : str
        Path to Exonerate's fastasort binary, optionally for sorting
        final FAA files (default None)
        
    Returns 
    -------
    df_alleles : pd.DataFrame
        Binary allele x genome table
    df_genes : pd.DataFrame
        Binary gene x genome table
    '''
    
    ''' Merge FAAs into one file with non-redundant sequences '''
    print 'Identifying non-redundant CDS sequences...'
    output_nr_faa = output_dir + '/' + name + '_nr.faa' # final non-redundant FAA files
    output_shared_headers = output_dir + '/' + name + '_redundant_headers.tsv' # records headers that have the same sequence
    output_missing_headers = output_dir + '/' + name + '_missing_headers.txt' # records headers without any seqeunce
    output_nr_faa = output_nr_faa.replace('//','/')
    output_shared_headers = output_shared_headers.replace('//','/')
    output_missing_headers = output_missing_headers.replace('//','/')
    non_redundant_seq_hashes, missing_headers = consolidate_cds(genome_faa_paths, output_nr_faa, 
                                                                output_shared_headers, output_missing_headers)
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
                                                shared_headers_file=output_shared_headers,
                                                fastasort_path=fastasort_path)
    # maps original headers to short names <name>_C#A#
    
    ''' Process gene/allele membership into binary tables '''
    output_allele_table = output_dir + '/' + name + '_strain_by_allele.csv.gz'
    output_gene_table = output_dir + '/' + name + '_strain_by_gene.csv.gz'
    output_allele_table = output_allele_table.replace('//','/')
    output_gene_table = output_gene_table.replace('//','/')
    df_alleles, df_genes = build_genetic_feature_tables(output_nr_clstr, genome_faa_paths, 
                              output_allele_table, output_gene_table, 
                              header_to_allele=header_to_allele)
    return df_alleles, df_genes
    

def consolidate_cds(genome_faa_paths, nr_faa_out, shared_headers_out, missing_headers_out=None):
    ''' 
    Combines CDS protein sequences for many genomes into a single file while
    without duplicate sequences to be clustered using cluster_cds (CD-Hit wrapper),
    Tracks headers that share the same sequence, and optionally headers without sequences.
    
    Parameters
    ----------
    genome_faa_paths : list
        Paths to genome FAA files to combine
    nr_faa_out : str
        Output path for combined non-redundant FAA file
    shared_headers_out : str
        Output path for shared headers TSV file
    missing_headers_out : str
        Output path for headers without sequences TXT file (default None)

    Returns
    -------
    non_redundant_seq_hashes : dict
        Maps non-redundant sequence hashes to a list of headers, in order observed
    missing_headers : list
        List of headers without any associated sequence
    '''
    non_redundant_seq_hashes = {} # maps sequence hash to headers of that sequence, in order observed
    encounter_order = [] # stores sequence hashes in order encountered
    missing_headers = [] # stores headers without sequences
    
    def process_header_and_seq(header, seq_blocks, output_file):
        ''' Processes a header/sequence pair against the running list of non-redundant sequences '''
        seq = ''.join(seq_blocks)
        if len(header) > 0 and len(seq) > 0: # valid header-sequence record
            seqhash = __hash_sequence__(seq)
            if seqhash in non_redundant_seq_hashes: # record repeated appearances of sequence
                non_redundant_seq_hashes[seqhash].append(header)
            else: # first encounter of a sequence, record to non-redundant FAA file
                encounter_order.append(seqhash)
                non_redundant_seq_hashes[seqhash] = [header]
                output_file.write('>' + header + '\n')
                output_file.write('\n'.join(seq_blocks) + '\n')
        elif len(header) > 0 and len(seq) == 0: # header without sequence
            missing_headers.append(header)
    
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
                
    ''' Save shared and missing headers to file '''
    with open(shared_headers_out, 'w+') as f_header_out:
        for seqhash in encounter_order:
            headers = non_redundant_seq_hashes[seqhash]
            if len(headers) > 1:
                f_header_out.write('\t'.join(headers) + '\n')
    if missing_headers_out:
        print 'Headers without sequences:', len(missing_headers)
        with open(missing_headers_out, 'w+') as f_header_out:
            for header in missing_headers:
                f_header_out.write(header + '\n')
                
    return non_redundant_seq_hashes, missing_headers
        
                
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
                             shared_headers_file=None, fastasort_path=None):
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
    shared_headers_file : str
        Path to shared headers. If provided, will expand the header-allele
        mapping to include headers that map to the same sequence/allele (default None)
    fastasort_path : str
        Path to Exonerate fastasort, used to optionally sort nr_faa (default None)
        
    Returns
    -------
    header_to_allele : dict
        Maps original headers to new allele names
    '''
    
    ''' Optionally, load up shared headers '''
    shared_headers = {} # maps representative header to synonym headers
    if shared_headers_file:
        with open(shared_headers_file, 'r') as f_share:
            for line in f_share:
                headers = line.strip().split('\t')
                representative_header = headers[0]
                synonym_headers = headers[1:]
                shared_headers[representative_header] = synonym_headers
    
    ''' Read through CLSTR file to map original headers to C#A# names '''
    header_to_allele = {} # maps headers to allele name (name_C#A#)
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
                    mapped_headers = [allele_header]
                    if allele_header in shared_headers: # if synonym headers are available
                        for synonym_header in shared_headers[allele_header]:
                            header_to_allele[synonym_header] = allele_name
                        mapped_headers += shared_headers[allele_header]
                    f_naming.write(allele_name + '\t' + ('\t'.join(mapped_headers)).strip() + '\n')
                    
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
    

def build_genetic_feature_tables(clstr_file, genome_faa_paths, allele_table_out=None, gene_table_out=None,
                                 shared_header_file=None, header_to_allele=None):
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
        Paths to genome FAA files originally combined and clustered (see consolidate_cds)
    allele_table_out : str
        Output path for binary allele x genome table, expect CSV or CSV.GZ (default None)
    gene_table_out : str
        Output path for binary gene x genome table, expect CSV or CSV.GZ (default None)
    shared_header_file : str
        Path to shared header TSV file, if synonym headers are not mapped
        in header_to_allele or header_to_allele is not provided (default None)
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
    
    ''' Load header to allele mapping from CLSTR, if not provided '''
    if header_to_allele is None:
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
    if shared_header_file:
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
        if gene != last_gene:
            gene_order.append(gene)
            last_gene = gene
    df_genes = pd.DataFrame(index=gene_order, columns=genome_order)
    print 'Genomes:', len(genome_order)
    print 'Alleles:', len(allele_order)
    print 'Genes:', len(gene_order)
        
    ''' Scan original genome file for allele and gene membership '''
    for i, genome_faa in enumerate(sorted(genome_faa_paths)):
        genome = faa_to_genome(genome_faa)
        genome_alleles = set(); genome_genes = set()
        with open(genome_faa, 'r') as f_faa:
            header = ''; seq = '' # track the sequence to skip over empty sequences
            for line in f_faa:
                ''' Load all alleles and genes per genome '''
                if line[0] == '>': # new header line encountered
                    if len(seq) > 0:
                        allele = header_to_allele[header] if header in header_to_allele \
                            else shared_header_to_allele[header]
                        gene = __get_gene_from_allele__(allele)
                        genome_alleles.add(allele)
                        genome_genes.add(gene)
                    header = __get_header_from_fasta_line__(line)
                    seq = '' # reset sequence
                else: # sequence line encountered
                    seq += line.strip()
            if len(seq) > 0: # process last record
                allele = header_to_allele[header] if header in header_to_allele \
                    else shared_header_to_allele[header]
                gene = __get_gene_from_allele__(allele)
                genome_alleles.add(allele)
                genome_genes.add(gene)
                    
            ''' Save to running table  '''
            print 'Updating genome', i+1, ':', genome, 
            print '\tAlleles:', len(genome_alleles), '\tGenes:', len(genome_genes)
            df_alleles.loc[genome_alleles, genome] = 1
            df_genes.loc[genome_genes, genome] = 1
    
    if allele_table_out:
        df_alleles.to_csv(allele_table_out)
    if gene_table_out:
        df_genes.to_csv(gene_table_out)
    return df_alleles, df_genes


def build_upstream_pangenome(genome_data, allele_names, output_dir, limits=(-50,3), name='Test', 
                             include_fragments=False, fastasort_path=None):
    '''
    Extracts nucleotides upstream of coding sequences for multiple genomes, 
    create <genome>_upstream.fna files in the same directory for each genome.
    Then, classifies/names them relative to gene clusters identified by coding sequence,  
    i.e. after build_cds_pangenome(). See extract_upstream_sequences() for more details.
    
    Parameters
    ----------
    genome_data : list
        List of 2-tuples (genome_gff, genome_fna) for use by extract_upstream_sequences
    allele_names : str
        Path to allele names file, should be named <name>_allele_names.tsv
    output_dir : str
        Path to directory to generate summary outputs.
    limits : 2-tuple
        Length of upstream region to extract, formatted (-X,Y). Will extract X 
        upstream bases (up to but excluding first base of start codon) and Y coding 
        bases (including first base of start codon), for total length of X+Y bases
        (default (-50,3))
    name : str
        Short header to prepend output summary files, ideally same as what
        was used in the build_cds_pangenome() (default 'Test')
    include_fragments : bool
        If true, include upstream sequences that are not fully available 
        due to contig boundaries (default False)
    fastasort_path : str
        Path to Exonerate's fastasort binary, optionally for sorting
        final FNA files (default None)
        
    Returns
    -------
    df_upstream : pd.DataFrame
        Binary upstream x genome table
    '''
    
    ''' Load header-allele name mapping '''
    print 'Loading header-allele mapping...'
    feature_to_allele = {}
    with open(allele_names, 'r') as f_all:
        for line in f_all:
            data = line.strip().split('\t')
            allele = data[0]; synonyms = data[1:]
            for synonym in synonyms:
                feature_to_allele[synonym] = allele
        
    ''' Generate upstream sequences '''
    print 'Extracting upstream sequences...'
    genome_upstreams = []
    for i, gff_fna in enumerate(genome_data):
        ''' Prepare output path '''
        genome_gff, genome_fna = gff_fna
        genome = genome_gff.split('/')[-1][:-4] # trim off path and .gff
        genome_dir = '/'.join(genome_gff.split('/')[:-1]) + '/' if '/' in genome_gff else ''
        genome_upstream_dir = genome_dir + 'derived/'
        if not os.path.exists(genome_upstream_dir):
            os.mkdir(genome_upstream_dir)
        genome_upstream = genome_upstream_dir + genome + '_upstream.fna'
            
        ''' Extract upstream sequences '''
        print i+1, genome
        genome_upstreams.append(genome_upstream)
        extract_upstream_sequences(genome_gff, genome_fna, genome_upstream, limits=limits,
                                   feature_to_allele=feature_to_allele, 
                                   include_fragments=include_fragments)
        
    ''' Consolidate non-redundant upstream sequences per gene '''
    print 'Identifying non-redundant upstream sequences per gene...'
    map_feature_to_gffid = lambda x: '|'.join(x.split('|')[:2]) # filter out locus tags
    feature_to_allele = {map_feature_to_gffid(k):v for k,v in feature_to_allele.items()}
    nr_upstream_out = output_dir + '/' + name + '_nr_upstream.fna'
    nr_upstream_out = nr_upstream_out.replace('//','/')
    df_upstream = consolidate_upstream(genome_upstreams, nr_upstream_out, feature_to_allele)
    
    ''' Optionally sort non-redundant upstream sequences file '''
    if fastasort_path:
        print 'Sorting sequences by header...'
        args = ['./' + fastasort_path, nr_upstream_out]
        with open(nr_upstream_out + '.tmp', 'w+') as f_sort:
            sp.call(args, stdout=f_sort)
        os.rename(nr_upstream_out + '.tmp', nr_upstream_out)
        
    ''' Save upstream x genome table '''
    upstream_table_out = output_dir + '/' + name + '_strain_by_upstream.csv.gz'
    upstream_table_out = upstream_table_out.replace('//','/')
    df_upstream.to_csv(upstream_table_out)
    return df_upstream
    

def consolidate_upstream(genome_upstreams, nr_upstream_out, feature_to_allele):
    '''
    Conslidates upstream sequences to a non-redundant set with respect 
    to each gene described by feature_to_allele (maps features to <name>_C#A#),
    then creates an upstream x genome binary table. Sequences in nr_upstream_out 
    are sorted by order encountered, not gene.
    
    Parameters
    ----------
    genome_upstreams : list
        List of paths to upstream sequences FNA to combine
    nr_upstream_out : str
        Path to output non-redundant upstream sequences as FNA
    feature_to_allele : dict
        Dictionary mapping headers to <name>_C#A# alleles
    
    Returns
    -------
    df_upstream : pd.DataFrame
         Binary upstream x genome table
    '''
    gene_to_unique_upstream = {} # maps gene:upstream_seq:upstream_seq_id (int)
    genome_to_upstream = {} # maps genome:upstream_name:1 if present (<name>_C#U#)
    
    with open(nr_upstream_out, 'w+') as f_nr_ups:
        for genome_upstream in genome_upstreams:
            ''' Infer genome name from genome filename '''
            genome = genome_upstream.split('/')[-1] # trim off full path
            genome = genome.split('_upstream')[0] # remove _upstream.fna footer
            genome_to_upstream[genome] = {}
            
            ''' Process genome's upstream record '''
            with open(genome_upstream, 'r') as f_ups: # reading current upstream
                header = ''; upstream_seq = ''
                for line in f_ups:
                    if line[0] == '>': # header line
                        if len(upstream_seq) > 0:
                            ''' Process header-seq to non-redundant <name>_C#U# upstream allele '''
                            feature = header.split('_upstream(')[0] # trim off "_upstream" footer
                            allele = feature_to_allele[feature] # get <name>_C#A# allele
                            gene = __get_gene_from_allele__(allele) # gene <name>_C# gene
                            if not gene in gene_to_unique_upstream:
                                gene_to_unique_upstream[gene] = {}
                            if not upstream_seq in gene_to_unique_upstream[gene]:
                                gene_to_unique_upstream[gene][upstream_seq] = len(gene_to_unique_upstream[gene])
                            upstream_id = gene + 'U' + str(gene_to_unique_upstream[gene][upstream_seq])
                            genome_to_upstream[genome][upstream_id] = 1
                            
                            ''' Write renamed sequence to temporary file '''
                            f_nr_ups.write('>' + upstream_id + '\n')
                            f_nr_ups.write(upstream_seq + '\n')

                        header = line[1:].strip(); upstream_seq = ''
                    else: # sequence line
                        upstream_seq += line.strip()
            
                ''' Process last record'''
                feature = header.split('_upstream(')[0] # trim off "_upstream" footer
                allele = feature_to_allele[feature] # get <name>_C#A# allele
                gene = __get_gene_from_allele__(allele) # gene <name>_C# gene
                if not gene in gene_to_unique_upstream:
                    gene_to_unique_upstream[gene] = {}
                if not upstream_seq in gene_to_unique_upstream[gene]:
                    gene_to_unique_upstream[gene][upstream_seq] = len(gene_to_unique_upstream[gene])
                upstream_id = gene + 'U' + str(gene_to_unique_upstream[gene][upstream_seq])
                genome_to_upstream[genome][upstream_id] = 1

                ''' Write renamed sequence to temporary file '''
                f_nr_ups.write('>' + upstream_id + '\n')
                f_nr_ups.write(upstream_seq + '\n')
    
    df_upstream = pd.DataFrame.from_dict(genome_to_upstream)
    return df_upstream

                
def extract_upstream_sequences(genome_gff, genome_fna, upstream_out, limits=(-50,3), 
                               feature_to_allele=None, allele_names=None, include_fragments=False):
    '''
    Extracts nucleotides upstream of coding sequences. Interprets GFFs as formatted by PATRIC:
        1) Assumes contigs are labeled "accn|<contig>". 
        2) Assumes protein features have ".peg." in the ID
        3) Assumes ID = fig|<genome>.peg.#
    Output features are named "<feature header>_upstream(<limit1>,<limit2>)". 
    
    Parameters
    ----------
    genome_gff : str
        Path to genome GFF file with CDS coordinates
    genome_fna : str
        Path to genome FNA file with contig nucleotides
    upstream_out : str
        Path to output upstream sequences FNA files
    limits : 2-tuple
        Length of upstream region to extract, formatted (-X,Y). Will extract X 
        upstream bases (up to but excluding first base of start codon) and Y coding 
        bases (including first base of start codon), for total length of X+Y bases
        (default (-50,3)) 
    feature_to_allele : dict
        Dictionary mapping original feature headers to <name>_C#A# short names,
        alternatively, the allele_names file can be provided (default None)
    allele_names : str
        Path to allele names file if feature_to_allele is not provided,
        should be named <name>_allele_names.tsv. If neither are provided,
        simply processes all features present in the GFF (default None)
    include_fragments : bool
        If true, include upstream sequences that are not fully available 
        due to contig boundaries (default False)
    '''
    
    ''' Load contig sequences '''
    contigs = {} # header to contig sequence
    with open(genome_fna, 'r') as f_fna:
        header = ''; seq = ''
        for line in f_fna:
            if line[0] == '>': # header encountered
                if len(seq) > 0: # save header-seq pair
                    contigs[header] = seq
                header = line.split()[0][1:]
                seq = ''
            else: # sequence line encountered
                seq += line.strip()
        if len(seq) > 0: # process last record
            contigs[header] = seq
            
    ''' Load header-allele name mapping '''
    map_feature_to_gffid = lambda x: '|'.join(x.split('|')[:2])
    if feature_to_allele: # dictionary provided directly
        feat_to_allele = {map_feature_to_gffid(k):v for k,v in feature_to_allele.items()}
    elif allele_names: # allele map file provided
        feat_to_allele = {}
        with open(allele_names, 'r') as f_all:
            for line in f_all:
                data = line.strip().split('\t')
                allele = data[0]; synonyms = data[1:]
                for synonym in synonyms:
                    gff_synonym = map_feature_to_gffid(synonym)
                    feat_to_allele[gff_synonym] = allele
    else: # no allele mapping, process everything
        feat_to_allele = None
                    
    ''' Parse GFF file for CDS coordinates '''
    complement = {'A': 'T', 'C': 'G', 'G': 'C', 'T': 'A', 
                  'W': 'W', 'S': 'S', 'R': 'Y', 'Y': 'R', 
                  'M': 'K', 'K': 'M', 'N': 'N'}
    for bp in complement.keys():
        complement[bp.lower()] = complement[bp].lower()
    reverse_complement = lambda s: (''.join([complement[base] for base in list(s)]))[::-1]
    feature_footer = '_upstream' + str(limits).replace(' ','')
    upstream_count = 0
    with open(upstream_out, 'w+') as f_ups:
        with open(genome_gff, 'r') as f_gff:
            for line in f_gff:
                line = line.strip()
                if len(line) > 0 and line[0] != '#':
                    contig, src, feat_type, start, stop, score, strand, phase, attr_raw = line.split('\t')
                    contig = contig.split('|')[-1] # accn|<contig> to just <contig>
                    start = int(start); stop = int(stop)
                    attrs = {} # key:value
                    for entry in attr_raw.split(';'):
                        k,v = entry.split('='); attrs[k] = v
                    gffid = attrs['ID']

                    ''' Verify allele has been mapped, and contig has been identified '''
                    if contig in contigs: 
                        if gffid in feat_to_allele or feat_to_allele is None:
                            contig_seq = contigs[contig]
                            ''' Identify upstream sequence '''
                            if strand == '+': # positive strand
                                ups_start = start + limits[0] - 1
                                ups_end = start + limits[1] - 1
                                upstream = contig_seq[ups_start:ups_end].strip()
                            else: # negative strand
                                ups_start = stop - limits[1]
                                ups_end = stop - limits[0] 
                                upstream = contig_seq[ups_start:ups_end].strip()
                                upstream = reverse_complement(upstream)
                                
                            ''' Save upstream sequence '''
                            if len(upstream) == -limits[0] + limits[1] or include_fragments:
                                feat_name = gffid + feature_footer
                                f_ups.write('>' + feat_name + '\n')
                                f_ups.write(upstream + '\n')
                                upstream_count += 1
                                   
    print 'Loaded upstream sequences:', upstream_count


def validate_gene_table(df_genes, df_alleles):
    '''
    Verifies that the gene x genome table is consistent with the
    corresponding allele x genome table.
    
    Parameters
    ----------
    df_genes : pd.DataFrame or str
        Either the gene x genome table, or path to the table as CSV or CSV.GZ
    df_alleles : pd.DataFrame or str
        Either the allele x genome table, or path to the table as CSV or CSV.GZ
    '''
    dfg = pd.read_csv(df_genes, index_col=0) if type(df_genes) == str else df_genes
    dfa = pd.read_csv(df_alleles, index_col=0) if type(df_alleles) == str else df_alleles
    print 'Validating gene clusters...'
    
    current_cluster = None; allele_data = []; 
    clusters_tested = 0; inconsistencies = 0
    for allele_row in dfa.fillna(0).itertuples(name=None):
        cluster = __get_gene_from_allele__(allele_row[0])

        if current_cluster is None: # initializing
            current_cluster = cluster
        elif current_cluster != cluster: # end of gene cluster
            alleles_all = np.array(allele_data)
            has_gene = alleles_all.sum(axis=0) > 0
            is_consistent = np.array_equal(has_gene, dfg.loc[current_cluster,:].fillna(0).values)
            clusters_tested += 1
            if not is_consistent:
                print 'Inconsistent', cluster
                print has_gene
                print dfg.loc[current_cluster,:].fillna(0).values
                inconsistencies += 1
            if clusters_tested % 1000 == 0:
                print '\tTested', clusters_tested, 'clusters'
            allele_data = []
            current_cluster = cluster
        allele_data.append(np.array(allele_row[1:]))
    
    ''' Process final line '''
    alleles_all = np.array(allele_data) 
    has_gene = alleles_all.sum(axis=0) > 0
    is_consistent = np.array_equal(has_gene, dfg.loc[current_cluster,:].fillna(0).values)
    if not is_consistent:
        print 'Inconsistent', cluster
        print has_gene
        print dfg.loc[current_cluster,:].fillna(0).values
        inconsistencies += 1
    print 'Inconsistencies:', inconsistencies


def validate_allele_table(df_alleles, genome_faa_paths, alleles_faa):
    '''
    Verifies that the allele x genome table is consistent with the original FAA files.
    
    Parameters
    ----------
    df_alleles : pd.DataFrame or str
        Either the allele x genome table, or path to the table as CSV or CSV.GZ
    genome_faa_paths : list
        Paths to genome FAA files originally combined and clustered
    alleles_faa : str
        Path to non-redundant sequences corresponding to df_alleles
    '''
    dfa = pd.read_csv(df_alleles, index_col=0) if type(df_alleles) == str else df_alleles
    
    ''' Pre-load hashes for non-redundant protein sequences '''
    print 'Loading non-redundant sequences...'
    seqhash_to_allele = {}
    with open(alleles_faa, 'r') as f_faa:
        header = ''; seq_blocks = []
        for line in f_faa:
            if line[0] == '>': # new sequence encountered
                if len(seq_blocks) > 0:
                    seqhash = __hash_sequence__(''.join(seq_blocks))
                    seqhash_to_allele[seqhash] = header
                header = line[1:].strip()
                seq_blocks = []
            else: # sequence encountered
                seq_blocks.append(line.strip())
        # process last record
        seqhash = __hash_sequence__(''.join(seq_blocks))
        seqhash_to_allele[seqhash] = header
                        
    ''' Validate individual genomes against table '''
    allele_counts = dfa.sum() # genome x total alleles
    for i, genome_faa in enumerate(sorted(genome_faa_paths)):
        print 'Validating genome', i+1, ':', genome_faa, 
        
        ''' Load all alleles present in the genome '''
        genome_alleles = set()
        with open(genome_faa, 'r') as f_faa:
            allele = ''; seq_blocks = []
            for line in f_faa:
                if line[0] == '>': # new sequence encountered
                    seq = ''.join(seq_blocks)
                    if len(seq) > 0:
                        seqhash = __hash_sequence__(seq)
                        allele = seqhash_to_allele[seqhash]
                        genome_alleles.add(allele)
                    seq_blocks = []
                else: # sequence encountered
                    seq_blocks.append(line.strip())
            # process last record
            seq = ''.join(seq_blocks)
            if len(seq) > 0:
                seqhash = __hash_sequence__(seq)
                allele = seqhash_to_allele[seqhash]
                genome_alleles.add(allele)
            
        ''' Check that identified alleles are consistent with the table '''
        genome = genome_faa.split('/')[-1][:-4]
        df_ga = dfa.loc[:,genome]
        table_alleles = set(df_ga.index[pd.notnull(df_ga)])
        test = table_alleles == genome_alleles
        print test, len(table_alleles), len(genome_alleles)

                          
def __get_gene_from_allele__(allele):
    ''' Converts <name>_C#A# allele to <name>_C# gene '''
    return 'A'.join(allele.split('A')[:-1])

def __get_header_from_fasta_line__(line):
    ''' Extracts a short header from a full header line in a fasta'''
    return line.split()[0][1:].strip()

def __hash_sequence__(seq):
    ''' Hashes arbitary length strings/sequences '''
    return hashlib.sha256(seq).hexdigest()
            
def __stream_stdout__(command):
    ''' Hopefully Jupyter-safe method for streaming process stdout '''
    process = sp.Popen(command, stdout=sp.PIPE, shell=True)
    while True:
        line = process.stdout.readline()
        if not line:
            break
        yield line.rstrip()
    