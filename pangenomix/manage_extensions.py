import os

def change_url_extensions(input_file, output_file, old_extension, new_extension):
    # Get the directory of the input file
    input_dir = os.path.dirname(input_file)

    with open(input_file, 'r') as file:
        urls = file.readlines()

    modified_urls = [url.strip().replace(old_extension, new_extension) for url in urls]

    # Create the full path to the output file in the same directory
    output_file_path = os.path.join(input_dir, output_file)

    with open(output_file_path, 'w') as out_file:
        out_file.writelines('\n'.join(modified_urls))


def rename_files_with_extension(folder_path, source_extension, target_extension):
    try:
        # Change to the specified directory
        os.chdir(folder_path)

        # Get a list of files with the source extension
        source_files = [f for f in os.listdir() if f.endswith(source_extension)]

        for file in source_files:
            # Generate the new file name by replacing the source extension with the target extension
            new_name = file.replace(source_extension, target_extension)

            # Rename the file
            os.rename(file, new_name)

        print("Renaming complete.")
    except Exception as e:
        print(f"An error occurred: {e}")