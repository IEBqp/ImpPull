# Copyright 2025 IEBqp
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os, sys, time, paramiko, argparse, stat
from gitignore_parser import parse_gitignore
from configparser import ConfigParser

#TODO: if the directory itself is in the .gitignore file, skip it as a whole but if its contents are in .gitignore still create an empty directory.

#TODO: Allow for username - password authentication (may have to use later in some other project).

#TODO: Make it easily usable in windows too.

class ImpPull():

    def __init__(self, username=None, host_ip=None, private_key=None, git_ignore=None, directory_to_be_cloned=None, clone_to=None):
        self.username = username
        self.host_ip= host_ip
        self.private_key = private_key
        self.git_ignore = git_ignore
        self.SSHClient = paramiko.SSHClient()
        self.SSHClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        print(host_ip,username,private_key)
        self.SSHClient.connect(host_ip,username=username,key_filename=private_key)
        self.SFTPClient = self.SSHClient.open_sftp()
        self.gitignore_matcher = parse_gitignore(git_ignore) if git_ignore != None else None
        self.clone_to = clone_to
        self.directory_to_be_cloned = directory_to_be_cloned

    def upload_directory(self):
        [_, files] = self._scan_directory_on_local(self.directory_to_be_cloned)
        replace_all_matching_files = False #False as default, will be asked in the loop whether user wants to replace the files or not
        skip_all_matching_files = False #False as default, will be asked in the loop whether user wants to replace the files or not
        while len(files) != 0:
            file = files.pop()
            #Check if file's directory exists, if it doesn't exit create the directories ourselves.
            path_to_put = os.path.join(self.clone_to, *file.split("/")[0:-1])
            self._remote_makedirs(path_to_put)
            #Check if the file that is being downloaded already exists, ask whether the user 
            #wants to replace this one, all the future ones or skip this one, skip all the future ones.
            try:
                existing_file = self.SFTPClient.stat(os.path.join(self.clone_to,file)).st_mode
            except:
                existing_file = None
                pass
            if existing_file and stat.S_ISREG(existing_file):
                while not (skip_all_matching_files or replace_all_matching_files):  # Input validation loop
                    print(f"File already exists at: {os.path.join(self.clone_to,file)}")
                    print("ConfigParser you like to:")
                    print("s) Skip")
                    print("sa) Skip all if exists")
                    print("r) Replace")
                    print("ra) Replace all if exists")
                    answer = input().lower()  # Handle lowercase input
                    if answer == "s":
                        break  # Skip this file
                    elif answer == "sa":
                        skip_all_matching_files = True
                        break
                    elif answer == "r":
                        self.SFTPClient.put(localpath=file,remotepath=os.path.join(self.clone_to,file))
                        break
                    elif answer == "ra":
                        replace_all_matching_files = True
                        break
                    else:
                        print("Invalid input. Please try again.")
                if skip_all_matching_files:
                    continue  # Skip to the next file
                if replace_all_matching_files:
                    self.SFTPClient.put(localpath=file,remotepath=os.path.join(self.clone_to,file))
            else:
                #Uploading the file depending on the condition mentioned above
                self.SFTPClient.put(localpath=file,remotepath=os.path.join(self.clone_to,file))
            print(file+" has been uploaded to "+path_to_put)
        self.SSHClient.close()

    def download_directory(self):
        [directories, files] = self._scan_directory_on_remote(self.directory_to_be_cloned)
        #Probably not the best way of doing this but meh, it works for my use case. 
        while len(directories) != 0:
            directory = directories.pop()
            [new_directories, new_files] = self._scan_directory_on_remote(directory)
            directories = list(set(new_directories+directories))
            files = files+new_files
            replace_all_matching_files = False #False as default, will be asked in the loop whether user wants to replace the files or not
            skip_all_matching_files = False #False as default, will be asked in the loop whether user wants to replace the files or not
            while len(files) != 0:
                file = files.pop()
                #Check if file's directory exists, if it doesn't exist create the directories ourselves.
                path_to_put = os.path.join(self.clone_to, *file.split("/")[0:-1])
                os.makedirs(path_to_put, exist_ok=True)
                
                #Check if the file that is being downloaded already exists, ask whether the user wants to: 
                # -replace this one -replace all the future ones -skip this one -skip all the future ones.
                if os.path.isfile(os.path.join(self.clone_to,file)):
                    if skip_all_matching_files or replace_all_matching_files:
                        answer = None
                    else:
                        print(
                            f"""
                            File already exists at location: {os.path.join(self.clone_to,file)}
                            Would you like to:
                            s) Skip
                            sa) Skip all if exists
                            r) Replace
                            ra) Replace all if exists
                            """
                        )
                        answer = input()
                    if answer == "s" or skip_all_matching_files:
                        continue
                    if answer == "sa":
                        skip_all_matching_files = True
                        continue
                    if answer == "r" or replace_all_matching_files:
                        pass
                    if answer == "ra":
                        replace_all_matching_files = True
                #Downloading the file depending on the condition mentioned above
                self.SFTPClient.get(remotepath=file,localpath=os.path.join(self.clone_to,file))
                print(file+" has been downloaded to "+path_to_put)
        self.SSHClient.close()

    def _scan_directory_on_remote(self,path):
        listings = self.SFTPClient.listdir_attr(path)
        directories, files = [], []
        for entry in listings:
            if self.gitignore_matcher != None:
                if self.gitignore_matcher(os.path.join(path,entry.filename)):
                    print(f"Found {path+'/'+entry.filename} in gitignore, skipping") 
                    continue
            if stat.S_ISDIR(entry.st_mode):
                directories.append(os.path.join(path,entry.filename)) 
            else:
                files.append(os.path.join(path,entry.filename))
        return [directories, files]
    
    def _scan_directory_on_local(self,path):
        found_files = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if self.gitignore_matcher != None:
                    if self.gitignore_matcher(os.path.join(root,file)):
                        print(f"Found {os.path.join(root,file)} in gitignore, skipping") 
                        continue
                found_files.append(os.path.join(root,file))
        return [[],found_files] #No directories will be returned from this method, and I still wanted to match the return style of _scan_directory_on_remote's

    def _remote_makedirs(self, path):
        temp_sftp = self.SSHClient.open_sftp()
        try:
            if path.startswith("/"):
                parts = path[1:].split("/")  # Remove leading slash and split
                current_path = "/"
            else:
                parts = path.split("/")
                current_path = ""

            for part in parts:
                if part:  # Skip empty parts (e.g., from double slashes)
                    try:
                        temp_sftp.chdir(part)  # Check if directory exists
                    except IOError:
                        try:
                            temp_sftp.mkdir(part)  # Create if it doesn't
                            temp_sftp.chdir(part)
                        except IOError as e:  # Handle potential mkdir errors
                            print(f"Error creating directory {part}: {e}")
                            raise  # Re-raise the exception after printing the error
        finally:
            temp_sftp.close()

def validate_config(config: ConfigParser):
    return set(config["IMPPULL"]) == {"username", "key", "address", "clonefrom", "clone", "to", "ignore"}

def norm_abs(rel, path):
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(rel,path))

def main():

    parser = argparse.ArgumentParser(
        prog="imppull",
        description="Easy cloning of remote directories tailored for a specific (my) use case",
        epilog="Created by IEBqp to be used in the development of Impake and many other projects"
    )

    parser.add_argument("-c","--clone", help="Path of the directory to be cloned.")

    parser.add_argument("-f","--clone_from", help="From [remote | local] determines whether you are cloning from your local machine to the remote one or the opposite")

    parser.add_argument("-ig", "--ignore", help="Gitignore file that will be parsed and files/directories will be ignored inside the file")

    parser.add_argument("-t", "--to", help="Path for the directory to be cloned to.")

    parser.add_argument(
        "-k", "--key", 
        help="""
        Private key location for the ssh connection:
        -k [path to private key] or --key [path to private key]
        """
    )

    parser.add_argument("-u", "--username", help="Username of the host server")
    parser.add_argument("-a", "--address", help="IP address of the host server")

    parser.add_argument(
        "-sc", "--bash", 
        help="""
        Bash script to execute on the server
        You must also provide a upload location using -t [path] or --to [path]
        """
    )

    parser.add_argument(
        "-conf", "--config", 
        help="""
        Config file path to define the key, host address etc. See the example_config.ini for further information.
        I really recommend having one config file per project just to be used for this.
        """
    )

    parser.add_argument(
        "-rel", "--relative_to", 
        help="""
        When ran using the bash script, this argument is sent automatically to then use the value for determining the absolute paths 
        of the relative paths you send in the arguments.
        """
    )

    args = parser.parse_args()
    config = ConfigParser()
    if args.config:
        config.read(norm_abs(args.relative_to,args.config))
        if validate_config(config) == False:
            raise Exception("Invalid config, check the example config file to see what you are missing.")

    if args.config == None:
        if args.address is None and args.config is None:
            raise Exception("No connection address provided, either provide a config file or an address")

        if args.key is None and args.config is None:
            raise Exception("No key provided, either provide a config file or a key")

        if args.username is None and args.config is None:
            raise Exception("No key provided, either provide a config file or a key")

        if args.clone is None or args.to is None:
            raise Exception("No clone path or to path provided, use -h clone or -h path for help")

        if args.clone_from.lower() not in ("local","remote"):
            raise Exception("Invalid from value, use 'local' or 'remote'")

    clone_from = args.clone_from if args.config is None else config["IMPPULL"]["CLONEFROM"]
    
    imppull = ImpPull(
        username = args.username if args.config == None else config["IMPPULL"]["USERNAME"],
        host_ip = args.address if args.config == None else config["IMPPULL"]["ADDRESS"],
        private_key = norm_abs(args.relative_to, args.key if args.config == None else config["IMPPULL"]["KEY"]),
        git_ignore = norm_abs(args.relative_to, args.ignore if args.config == None else config["IMPPULL"]["IGNORE"]),
        directory_to_be_cloned = norm_abs(args.relative_to, args.clone if args.config == None else config["IMPPULL"]["CLONE"]) if clone_from == "local" else args.clone if args.config == None else config["IMPPULL"]["CLONE"],
        clone_to = norm_abs(args.relative_to, args.to if args.config == None else config["IMPPULL"]["TO"]) if clone_from == "remote" else args.to if args.config == None else config["IMPPULL"]["TO"]
        #Most disgusting lines of code in this file are the 2 above lines, it works though so I don't really care atm
    )

    if args.config == None:
        if args.clone_from.lower() == "remote":
            #Clones from the remote machine to the local one.
            imppull.download_directory()

        if args.clone_from.lower() == "local":
            #Clones from the local machine to the remote one.
            imppull.upload_directory()
    else:
        print(config["IMPPULL"]["CLONEFROM"].lower())
        if config["IMPPULL"]["CLONEFROM"].lower() == "remote":
            #Clones from the remote machine to the local one.
            imppull.download_directory()

        if config["IMPPULL"]["CLONEFROM"].lower() == "local":
            #Clones from the local machine to the remote one.
            imppull.upload_directory()
        

if __name__ == "__main__":
    main()