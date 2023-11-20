import numpy as np
import pandas as pd
from Bio import SeqIO
import ast


def create_alleles_fasta(allele_npz_file, gene_npz_label_file, allele_npz_label_file, input_faa, output_faa):

    # This function runs the whole pipeline that allows the user to obtain a list
    # of the most highly expressed alleles of each gene in the pangenome

    allele_occurence_count = count_allele_occurence(allele_npz_file)

    genes_alleles_pairs = identify_gene_allele_rows(gene_npz_label_file, allele_npz_label_file)

    highest_expression_rows = find_highest_expression(allele_occurence_count, genes_alleles_pairs)

    highest_expression_names = find_allele_names(highest_expression_rows, allele_npz_label_file)

    filter_sequences(input_faa, highest_expression_names, output_faa)



def filter_sequences(input_faa, highest_expression_names, output_faa):
    # Creates fasta file with alleles that have the highest expression levels

    # Extract the allele names from the DataFrame
    allele_names = highest_expression_names.tolist()

    # Read the input FAA file and filter sequences based on allele names
    filtered_sequences = []
    for record in SeqIO.parse(input_faa, 'fasta'):
        allele_name = record.id.split('|')[0]  # Extract allele name from the record ID
        if allele_name in allele_names:
            filtered_sequences.append(record)

    print("\nCreated a FASTA file with all the highly expressed alleles. Success!")

    # Write the filtered sequences to the output FAA file
    SeqIO.write(filtered_sequences, output_faa, 'fasta')



def find_allele_names(highest_expression_rows, allele_npz_label_file):
    # "Translates" the row numbers to cluster names

    # Read the allele labels file with specified encoding
    allele_labels_df = pd.read_csv(allele_npz_label_file, header=None, names=['allele_name'])

    # Create a DataFrame with gene indices
    highest_expression_rows['gene'] = highest_expression_rows['gene'].astype(int)

    # Merge highest_expression and allele_labels DataFrames based on the 'gene' and 'highest_expression' columns
    highest_expression_names = pd.merge(highest_expression_rows, allele_labels_df, left_on='highest_expression', right_index=True)

    print("\nFound the alleles with the highest expression per gene")

    return highest_expression_names['allele_name']



def find_highest_expression(row_counts_df, gene_allele_rows_df):
    # Initialize an empty list to store the results
    output_data = []

    # Iterate over rows in gene_allele_rows
    for index, row in gene_allele_rows_df.iterrows():
        gene = row['gene']
        
        # Check if allele_index is a list or a string representation of a list
        if isinstance(row['allele_index'], list):
            allele_indices = row['allele_index']
        else:
            allele_indices = ast.literal_eval(row['allele_index'])  # Convert string representation to a list
        
        # Find the row with the highest count for each gene
        highest_rows = row_counts_df.loc[allele_indices, 'count'].idxmax()
        
        # Check if there is a tie
        is_tie = row_counts_df.loc[allele_indices, 'count'].duplicated().any()
        
        # Append the result to the output data list
        if is_tie:
            highest_rows = row_counts_df.loc[allele_indices, 'count'].idxmax()
            output_data.append({'gene': gene, 'highest_expression': highest_rows.tolist()})
        else:
            output_data.append({'gene': gene, 'highest_expression': highest_rows})

    # Create a DataFrame from the output data list
    output_df = pd.DataFrame(output_data)

    return output_df


def identify_gene_allele_rows(gene_npz_label_file, allele_npz_label_file):
    # Identifies all the alleles per gene

    # Read gene names from the gene file
    gene_df = pd.read_csv(gene_npz_label_file, header=None, names=['gene_name'])

    # Read allele names from the allele file
    allele_df = pd.read_csv(allele_npz_label_file, header=None, names=['allele_name'])

    # Create a DataFrame with gene indices
    gene_df['gene'] = gene_df.index

    # Extract gene names from allele names
    allele_df['gene_name'] = allele_df['allele_name'].str.extract(r'([^A]+)')

    # Merge gene and allele DataFrames based on the common 'gene_name' column
    merged_df = pd.merge(allele_df, gene_df, on='gene_name', how='left')

    # Create a column 'allele_index' as a list of allele indices
    merged_df['allele_index'] = merged_df.groupby('gene')['allele_name'].transform(lambda x: x.index.tolist())

    # Group by gene and aggregate the 'allele_index' column as a list
    result_df = merged_df.groupby('gene')['allele_index'].agg(list).reset_index()

    result_df['gene'] = result_df['gene'].astype(int)

    result_df['allele_index'] = result_df['allele_index'].apply(lambda x: [int(i) for i in x])

    print("\nIdentified all alleles per genome")

    return result_df



def count_allele_occurence(allele_npz_file):
    # Counts the occurence of each allele in all genomes

    # Load the data
    with np.load(allele_npz_file) as data:
        row_indices = data['row']
        col_indices = data['col']

    # Create a DataFrame to count occurrences of each row index
    df = pd.DataFrame({'allele_index': row_indices, 'col': col_indices})

    # Add a column 'count' representing the number of occurrences for each row index
    df['count'] = df.groupby('allele_index').transform('size')

    # Drop duplicate rows to keep unique row indices
    df_unique = df.drop_duplicates(subset=['allele_index', 'count'])

    # Remove the 'col' column
    df_unique = df_unique.drop(columns=['col'])

    # Order the DataFrame by the 'row' column
    df_unique = df_unique.sort_values(by='allele_index')

    # Reset the index to ensure consistency
    df_unique = df_unique.reset_index(drop=True)

    print("\nCounted allele occurence")

    return df_unique