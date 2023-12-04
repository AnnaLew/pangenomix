import pandas as pd
import pangenome_analysis
import matplotlib.pyplot as plt

def calculate_mean(df_pan_core,jpgName):

    # Calculate the mean value for each column
    mean_values = df_pan_core.mean()

    # Create a new DataFrame with mean values and use the same column names
    mean_df = pd.DataFrame([mean_values], columns=df_pan_core.columns)

    # Save the result to a new CSV file
    # mean_df.to_csv(output_csv, index=False)

    # Calculate the number of columns and split the DataFrame
    num_columns = mean_df.shape[1]
    half_columns = num_columns // 2
    
    # Split the DataFrame into two parts
    Pan = mean_df.iloc[:, :half_columns]
    Core = mean_df.iloc[:, half_columns:]

    #Transpose the DataFrame so that rows become columns#
    Pan_trans = Pan.T
    Core_trans = Core.T
    pan = Pan_trans.reset_index(drop=True)
    pan.index = pan.index + 1 
    core = Core_trans.reset_index(drop=True)
    core.index = core.index + 1

    #plot
    plt.plot(pan, label='Pangenome size')
    plt.plot(core,label='Core gene size')
    plt.xlabel('number of genomes')
    plt.ylabel('number of genes')
    plt.legend()

    # Generate the filename based on user input
    filename = f'{jpgName}_plot.png'
    plt.savefig(filename)
    
    return mean_df
