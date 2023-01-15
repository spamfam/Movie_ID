import os
import re
from imdb import Cinemagoer, IMDbDataAccessError

search = Cinemagoer()

# Open the error log file for writing
with open("error.log", "w") as log:
    # Iterate through the directory and its subdirectories
    for root, dirs, files in os.walk(os.getcwd()):
        for dir in dirs:
            # Check if the directory name already includes an IMDb ID number
            match = re.search(r'\{imdb-tt\d+\}|\(No IMDB\)', dir)
            if not match:
                try:
                    # Search for the movie ID
                    result = search.search_movie(dir)
                    # If no search result, skip directory
                    if len(result)==0:
                        log.write("Movie {} not found, skipping...\n".format(dir))
                        continue
                except ValueError as error:
                    # Handle the case where the movie name is not valid
                    log.write("Error searching movie {}: {}\n".format(dir, error))
                    continue
                except Exception as error:
                    # Handle other errors
                    log.write("Error: {}\n".format(error))
                    continue
                except IMDbDataAccessError as error:
                    # Handle the case where there is an error accessing IMDB 
                    log.write("Error searching movie {}: {}\n".format(dir, error))
                    continue

                # Get the IMDb ID
                imdb_id = result[0].movieID
                # Construct the new directory name
                new_dir_name = dir + " {imdb-tt" + imdb_id + "}"

                try:
                    # Rename the directory
                    os.rename(os.path.join(root, dir), os.path.join(root, new_dir_name))
                except Exception as error:
                    # Handle errors while renaming directory
                    log.write("Error renaming directory {}: {}\n".format(dir, error))
                    continue
                
                os.chdir(os.path.join(root, new_dir_name))
                # Reassign the files variable to the new directory
                files = os.listdir(os.getcwd())
                # List file types to search
                extensions = ('.mp4', '.mkv', '.avi', '.srt', '.idx', '.sub', '.png', '.jpg', '.jpeg')

                # Iterate through the files in the directory
                for file in files:
                    # Check if file matches extensions
                    if file.endswith(extensions):
                        # Check if file name contain the original folder name
                        if dir in file:
                            try:
                                # Construct the new file name
                                new_file_name = file.split(".")[0] + " {imdb-tt" + imdb_id + "}." + file.split(".")[-1]
                                # Rename the file
                                os.rename(file, new_file_name)
                            except Exception as error:
                                # Handle errors while renaming files
                                log.write("Error renaming file {}: {}\n".format(file, error))
                                continue

                # Go back to the parent directory
                os.chdir('..')