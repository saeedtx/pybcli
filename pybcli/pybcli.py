#!/usr/bin/env python3
"""
CLI tool to manage and execute bash functions locally or over SSH
Author: Saeed Mahameed <saeed@kernel.org>
Date: 2024-12-13
Usage: bcli <command> [<args>]
       bcli import path [namespace] # Import a file or directory into a namespace
       bcli exec [--ssh server] namespace file function [args...] # Execute a function from a file in a namespace
       bcli info [-v] [namespace] [file] [function] # Display configuration information
       bcli purge # Purge non-existing files from metadata
       bcli remove namespace [file] # Remove a namespace or a specific file within a namespace
       bcli install-bash-completion # Install bash completion script
       bcli [TAB] [TAB] # Provide bash completion
"""
import argparse
import select
import subprocess
import os
import sys
import yaml
import argcomplete  # Add import for argcomplete
import re
import tempfile
import json
import traceback

class Pybcli:
    def __init__(self, home_dir=None, sys_dir=None):
        self.home_dir = home_dir or os.path.expanduser("~/.pybcli")
        self.sys_dir = sys_dir or "/etc/pybcli"
        self.home_metadata_file = os.path.join(self.home_dir, "metadata.yaml")
        self.sys_metadata_file = os.path.join(self.sys_dir, "metadata.yaml")

    def _reslove_name_space(self, path, namespace):
        if namespace and namespace != "":
            return namespace
        if os.path.isdir(path):
            return os.path.basename(path)
        return "default"

    def handle_import(self, path, location, namespace):
        # Determine the base directory based on location
        conf_dir = self.sys_dir if location == "sys" else self.home_dir
        os.makedirs(conf_dir, exist_ok=True)

        # Update metadata
        metadata_file = self.sys_metadata_file if location == "sys" else self.home_metadata_file
        metadata = self.load_metadata(is_sys=(location == "sys"))
        print(f"Importing '{path}' into namespace '{namespace}' at '{metadata_file}'")
        namespace = self._reslove_name_space(path, namespace)
        if namespace not in metadata:
            metadata[namespace] = {}

        if os.path.isdir(path):
            # Import all bash files in the directory
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(".sh"):
                        file_path = os.path.join(root, file)
                        fname = os.path.splitext(os.path.basename(file_path))[0]
                        metadata[namespace][fname] = os.path.abspath(file_path)
                        print(f"File '{os.path.abspath(file_path)}' has been successfully imported into namespace '{namespace}/{fname}'")
        else:
            # Import a single file
            fname = os.path.splitext(os.path.basename(path))[0]
            metadata[namespace][fname] = os.path.abspath(path)
            print(f"File '{os.path.abspath(path)}' has been successfully imported into namespace '{namespace}/{fname}'")

        with open(metadata_file, 'w') as mf:
            yaml.safe_dump(metadata, mf)
            mf.close()
        print(f"Metadata updated for namespace '{namespace}' at '{metadata_file}'")

    def load_metadata(self, is_sys = False):
        metadata_file = self.sys_metadata_file if is_sys else self.home_metadata_file
        metadata = {}
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as mf:
                metadata = yaml.safe_load(mf) or {}
                mf.close()
        return metadata

    def load_all_metadata(self):
        home_metadata = self.load_metadata(is_sys=False)
        sys_metadata = self.load_metadata(is_sys=True)
        # merge sys metadata with home metadata
        for ns, files in sys_metadata.items():
            if ns in home_metadata:
                home_metadata[ns].update(files)
            else:
                home_metadata[ns] = files
        return home_metadata

    def bash_popen(self, file, func, *args):
        # Execute the function from the file
        command = f"set -e; source {file} && {func} {' '.join(map(str, args))} && wait"
        file_dir = os.path.dirname(file)
        return subprocess.Popen(["bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=file_dir)

    def resolve_includes(self, main_file, file_path, seen_files=None):
        if seen_files is None:
            seen_files = set()
        #print(f"Resolving includes in {file_path}")
        try:
            with open(file_path, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"Error: resolve_includes File {file_path} not found", file=sys.stderr)
            return []

        include_re = re.compile(r"^\s*(?:\.|source)\s+([^\s;]+)", re.MULTILINE)
        includes = []
        for match in include_re.finditer(content):
            include_line = match.group(0).strip().split(';')[0]  # Capture only the include statement
            include_path = match.group(1)
            full_path = os.path.abspath(os.path.join(os.path.dirname(main_file), include_path))
            # Ignore external files and only process internal includes that are forward from the file being run
            if not os.path.exists(full_path) or not full_path.startswith(os.path.dirname(main_file)):
                continue
            if full_path not in seen_files:
                seen_files.add(full_path)
                includes.append({
                    'line_number': content[:match.start()].count('\n') + 1,
                    'include_line': include_line,
                    'include_path': include_path,
                    'full_path': full_path,
                    'included_from': file_path
                })
                # Recursively resolve includes in the included file
                includes.extend(self.resolve_includes(main_file, full_path, seen_files))
        return includes

    def ssh_popen(self, remote, file, func, *args):
        # Open a persistent SSH connection using ControlMaster
        fname = os.path.splitext(os.path.basename(file))[0]
        parent_pid = os.getppid()
        ssh_control_path = tempfile.mktemp(prefix=f"bclissh-{parent_pid}-")
        ssh_command = [
            "ssh", "-MNf", "-o", f"ControlPath={ssh_control_path}", "-o", "ControlMaster=yes", remote
        ]
       # print(f"Opening persistent SSH connection to {remote}: {ssh_control_path}...")
        subprocess.run(ssh_command, check=True)

        # Create a temporary directory on the remote machine
        remote_temp_dir = f"/tmp/{fname}_{func}_{remote.replace('@', '_')}"
        ssh_mkdir_command = [
            "ssh", "-o", f"ControlPath={ssh_control_path}", remote, f"mkdir -p {remote_temp_dir}"
        ]
        #print(f"Creating temporary directory {remote_temp_dir} on {remote}...")
        subprocess.run(ssh_mkdir_command, check=True)

        # Send the bash file and its includes using SCP via the persistent connection
        remote_file = os.path.join(remote_temp_dir, os.path.basename(file))
        scp_command = [
            "scp", "-o", f"ControlPath={ssh_control_path}", file, f"{remote}:{remote_file}"
        ]
        #print(f"Transferring {file} to {remote}:{remote_file}...")

        result = subprocess.run(scp_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"Error transferring {file} to {remote}:{remote_file}")
            print(result.stderr)
            return result.returncode

        # Scan the file for includes and transfer them as well
        #print(f"Resolving includes for {file}...")
        includes = self.resolve_includes(file, file)
        #print(f"Resolved  includes for {file}...")
        for include in includes:
            include_file = include['full_path']
            include_path = include['include_path']
            relative_include_dir = os.path.dirname(include_path)
            remote_include_dir = os.path.join(remote_temp_dir, relative_include_dir)
            remote_include_file = os.path.join(remote_include_dir, os.path.basename(include_file))
            # Create the directory structure on the remote machine
            ssh_mkdir_command = [
                "ssh", "-o", f"ControlPath={ssh_control_path}", remote, f"mkdir -p {remote_include_dir}"
            ]
            #print(f"Creating directory {remote_include_dir} on {remote}...")
            subprocess.run(ssh_mkdir_command, check=True)
            # Transfer the include file
            scp_command = [
                "scp", "-o", f"ControlPath={ssh_control_path}", include_file, f"{remote}:{remote_include_file}"
            ]
            #print(f"Transferring {include_file} to {remote}:{remote_include_file}...")
            result = subprocess.run(scp_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                print(f"Error transferring {file} to {remote}:{remote_file}")
                print(result.stderr)
                return result.returncode

        # Execute the function via the persistent SSH connection
        remote_command = f"bash -c 'set -e; cd {remote_temp_dir} && source {os.path.basename(file)} && {func} {' '.join(map(str, args))}' && wait"
        exec_command = [
            "ssh", "-o", f"ControlPath={ssh_control_path}", remote, remote_command
        ]
        #print(f"Executing command: {remote_command}")
        process = subprocess.Popen(exec_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        process.ssh_control_path__ = ssh_control_path
        return process

    def handle_exec(self, remote, namespace, fname, func, *args):
        namespace = namespace or "default"

        metadata = self.load_all_metadata()
        if namespace not in metadata or fname not in metadata[namespace]:
            raise FileNotFoundError(f"File '{fname}' not found in namespace '{namespace}'")

        file = metadata[namespace][fname]
        if args and len(args) and args[0] == '--help':
            file_metadata = self.scan_bash_file(file)
            for function in file_metadata['functions']:
                if function['name'] == func:
                    description = function['annotations'].get('description') or ""
                    args_annotation = function['annotations'].get('args')
                    opts_annotation = function['annotations'].get('opts')
                    if args_annotation:
                        print(f"usage: {func} {args_annotation} // {description}")
                        if opts_annotation:
                            print(f"options: {opts_annotation}")
                        return 0

        process = None
        # TODO: handle return code properly
        rc = 127
        try:
            if remote:
                process = self.ssh_popen(remote, file, func, *args)
            else:
                process = self.bash_popen(file, func, *args)
            # Stream the output and errors while the command is running
            while True:
                reads = [process.stdout.fileno(), process.stderr.fileno()]
                ret = select.select(reads, [], [])
                for fd in ret[0]:
                    if fd == process.stdout.fileno():
                        output = process.stdout.readline()
                        if output:
                            print(output, end="")
                    if fd == process.stderr.fileno():
                        error = process.stderr.readline()
                        if error:
                            print(error, end="")
                if process.poll() is not None:
                    break

            # Print any remaining errors
            stdout = process.stdout.read()
            if stdout:
                print(stdout)
            stderr = process.stderr.read()
            if stderr:
                print(stderr)
            rc = process.poll()
            #print(f"Command execution complete with return code: {rc}")
        except subprocess.CalledProcessError as e:
            print(f"Command error: {e}")
        except FileNotFoundError as e:
            print(f"Error: File {file} not found")
            print(f"An unexpected error occurred: {e}")
            traceback.print_exc()

        except KeyboardInterrupt:
            print("Execution interrupted")
            rc = 130
            if not process:
                pass
            process.kill()
            process.wait()
            print(f"Command execution complete with return code: {process.returncode}")
            stdout = process.stdout.read()
            if stdout:
                print("--- STDOUT END ---")
                print(stdout)
            stderr = process.stderr.read()
            if stderr:
                print("--- STDERR END ---")
                print(stderr)
            rc = process.returncode if process.returncode else 130
        finally:
            if process:
                process.stdout.close()
                process.stderr.close()
            if process and hasattr(process, 'ssh_control_path__'):
                # Close the persistent SSH connection
                close_command = ["ssh", "-O", "exit", "-o", f"ControlPath={process.ssh_control_path__}", remote]
                #print("Closing persistent SSH connection...")
                subprocess.run(close_command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return rc

    def scan_bash_file(self, file_path):
        # Scan a bash file and extract metadata
        if not os.path.exists(file_path):
            print(f"{file_path} doesn't exist. Please run bcli purge", file=sys.stderr)
            return {}

        with open(file_path, 'r') as f:
            content = f.read()

        # Patterns for global and function-specific annotations
        global_annotation_re = re.compile(r"#bcli:\s+(\w+)\s+(.*)")
        function_re = re.compile(r"(?m)^\s*(\w+)\s*\(\s*\)\s*\{")
        func_annotation_re = re.compile(r"#bcli:func\s+(\w+)\s+(.*)")

        # Extract global annotations
        global_annotations = {}
        for match in global_annotation_re.finditer(content):
            global_annotations[match.group(1)] = match.group(2)

        # Extract function metadata
        functions = []
        for match in function_re.finditer(content):
            name = match.group(1)
            annotations = {}

            # Find function-specific annotations immediately preceding the function definition
            func_start_index = match.start()
            preceding_lines = content[:func_start_index].splitlines()
            preceding_lines.reverse()
            for line in preceding_lines:
                annotation_match = func_annotation_re.match(line)
                if annotation_match:
                    annotations[annotation_match.group(1)] = annotation_match.group(2)
                elif line.strip() != "" and not line.strip().startswith('#'):
                    # Stop if we hit a non-annotation or non-comment line
                    break
            functions.append({'name': name, 'annotations': annotations})

        # Extract includes
        includes = self.resolve_includes(file_path, file_path)

        file_metadata = {
            'file': file_path,
            'global_annotations': global_annotations,
            'functions': functions,
            'includes': includes
        }

        return file_metadata

    def handle_info(self, verbosity=1, namespace=None, fname=None, func=None):
        # Print the contents of the config YAML files for both home and sys
        for name in ['home', 'sys']:
            metadata = self.load_metadata(is_sys=(name == 'sys'))
            print(f"--- {name.upper()} CONFIG ---")
            for ns, files in metadata.items():
                    if namespace and ns != namespace:
                        continue
                    print(f"Namespace: {ns}")
                    for file_name, file_path in files.items():
                        if fname and file_name != fname:
                            continue
                        print(f"  {file_name}: {file_path}")
                        if verbosity >= 1:
                            file_metadata = self.scan_bash_file(file_path)
                            if not file_metadata:
                                continue
                            if verbosity == 2:
                                for function in file_metadata['functions']:
                                    if func and function['name'] != func:
                                        continue
                                    description = function['annotations'].get('description') or ""
                                    print(f"    - {function['name'] : <25} {description}")
                            elif verbosity >= 3:
                                print("    Metadata:")
                                print(json.dumps(file_metadata, indent=4))

    def handle_purge(self):
        # Load metadata for both home and sys
        home_metadata = self.load_metadata(is_sys=False)
        sys_metadata = self.load_metadata(is_sys=True)

        # Function to purge non-existing files from metadata
        def purge_metadata(metadata):
            purged_metadata = {}
            for namespace, files in metadata.items():
                purged_files = {fname: fpath for fname, fpath in files.items() if os.path.exists(fpath)}
                if purged_files:
                    purged_metadata[namespace] = purged_files
            return purged_metadata

        # Purge home metadata
        if home_metadata:
            purged_home_metadata = purge_metadata(home_metadata)
            with open(self.home_metadata_file, 'w') as mf:
                yaml.safe_dump(purged_home_metadata, mf)
                mf.close()
            print(f"Purged home metadata at '{self.home_metadata_file}'")

        # Purge sys metadata
        if sys_metadata:
            purged_sys_metadata = purge_metadata(sys_metadata)
            # check permissions
            if os.geteuid() != 0:
                print("You need to be root to purge sys metadata")
                return
            with open(self.sys_metadata_file, 'w') as mf:
                yaml.safe_dump(purged_sys_metadata, mf)
                mf.close()
            print(f"Purged sys metadata at '{self.sys_metadata_file}'")

    def handle_remove(self, namespace, fname=None):
        # Load metadata for both home and sys
        home_metadata = self.load_metadata(is_sys=False)
        sys_metadata = self.load_metadata(is_sys=True)

        def remove_from_metadata(metadata):
            if namespace in metadata:
                if fname:
                    if fname in metadata[namespace]:
                        del metadata[namespace][fname]
                        if not metadata[namespace]:  # Remove namespace if empty
                            del metadata[namespace]
                        return True
                else:
                    del metadata[namespace]
                    return True
            return False

        # Remove from home metadata
        home_updated = remove_from_metadata(home_metadata)
        if home_updated:
            with open(self.home_metadata_file, 'w') as mf:
                yaml.safe_dump(home_metadata, mf)
                mf.close()
            print(f"Updated home metadata at '{self.home_metadata_file}'")

        # Remove from sys metadata
        sys_updated = remove_from_metadata(sys_metadata)
        if sys_updated:
            # check permissions
            if os.geteuid() != 0:
                print("You need to be root to modify sys metadata")
                return
            with open(self.sys_metadata_file, 'w') as mf:
                yaml.safe_dump(sys_metadata, mf)
                mf.close()
            print(f"Updated sys metadata at '{self.sys_metadata_file}'")

        if not home_updated and not sys_updated:
            print(f"Namespace '{namespace}' or file '{fname}' not found in metadata")

def arg_complete(comp_cword, prev, curr, comp_words):
    if comp_cword == 1:
        options = ["import", "remove", "exec", "info", "purge", "install-bash-completion"]
        return [f for f in options if f.startswith(curr)]
    #comp_words = comp_words.split()
    cmd = comp_words[1] or ''
    # Custom argument completion logic
    if cmd == 'import':
        # Provide completion for import command
        #print(f"comp_cword: {comp_cword}, prev: {prev}, curr: {curr}, comp_words: {comp_words}")
        if comp_cword > 3:
            return []
        if prev == "import": # handled in the dump_completion_script function
                return []
        pybcli = Pybcli()
        home_metadata = pybcli.load_metadata(is_sys=False)
        home_namespaces = list(home_metadata.keys())
        options = [f"home.{ns}" for ns in home_namespaces]

        sys_metadata = pybcli.load_metadata(is_sys=True)
        sys_namespaces = list(sys_metadata.keys())

        # add sys. prefix to sys namespaces
        options += [f"sys.{ns}" for ns in sys_namespaces]
        for ns in home_namespaces + sys_namespaces:
                return [f for f in options if f.startswith(curr)]
    elif cmd == 'exec' or cmd == 'remove' or cmd == 'info':
        # remove --ssh server from comp_words
        # find the index of --ssh
        if '--ssh' in comp_words:
            ssh_index = comp_words.index('--ssh')
            comp_words.pop(ssh_index)  # Remove '--ssh'
            comp_cword -= 1
            if ssh_index < len(comp_words):
                comp_words.pop(ssh_index)  # Remove the word after '--ssh'
                comp_cword -= 1

        # Provide completion for exec command
        if comp_cword == 2:
            # Provide completion for namespaces
            pybcli = Pybcli()
            metadata = pybcli.load_all_metadata()
            namespaces = list(metadata.keys())
            return [f for f in namespaces if f.startswith(curr)]
        elif comp_cword == 3:
            # Provide completion for files
            pybcli = Pybcli()
            namespace = comp_words[2]
            metadata = pybcli.load_all_metadata()
            if namespace in metadata:
                files = list(metadata[namespace].keys())
                return [f for f in files if f.startswith(curr)]
        elif comp_cword == 4:
            # Provide completion for functions
            pybcli = Pybcli()
            namespace = comp_words[2]
            file = comp_words[3]
            metadata = pybcli.load_all_metadata()
            if namespace in metadata and file in metadata[namespace]:
                file_path = metadata[namespace][file]
                file_metadata = pybcli.scan_bash_file(file_path)
                if file_metadata:
                    functions = [f['name'] for f in file_metadata['functions']]
                    return [f for f in functions if f.startswith(curr)]
        elif comp_cword > 4:
            # Provide completion for function arguments and options
            pybcli = Pybcli()
            namespace = comp_words[2]
            file = comp_words[3]
            func = comp_words[4]
            metadata = pybcli.load_all_metadata()
            if namespace in metadata and file in metadata[namespace]:
                file_path = metadata[namespace][file]
                file_metadata = pybcli.scan_bash_file(file_path)
                if file_metadata:
                    for function in file_metadata['functions']:
                        if function['name'] == func:
                            args_annotation = function['annotations'].get('args')
                            opts_annotation = function['annotations'].get('opts')
                            if args_annotation:
                                args_list = args_annotation.split()
                                if comp_cword - 5 < len(args_list):
                                    args_list = [ args_list[comp_cword - 5] ]
                                    return [f for f in args_list if f.startswith(curr)]
                            if opts_annotation:
                                print(f"curr: {curr}", file=sys.stderr)
                                opts_list = opts_annotation.split()
                                return [f for f in opts_list if f.startswith(curr)]
    return []

def install_bash_completion(system_wide=True):
    bash_completion_script = """
    _pybcli_completion() {
        local cur prev words cword
        _get_comp_words_by_ref -n : cur prev words cword
        # return files if import
        [[ $cword -eq 2 ]] && [ "$prev" == "import" ] && {
            COMPREPLY=($(compgen -- "$cur"))
            return
        }
        [[ $cword -eq 2 ]] && [ "$prev" == "exec" ] && COMPREPLY=( $(compgen -W "--ssh" -- "$cur" ) )
        [[ $cword -eq 2 ]] && [ "$prev" == "exec" ] && [[ "$cur" == -* ]] && return
        [[ $cword -eq 3 ]] && [ "$prev" == "--ssh" ] && {
            COMPREPLY=($(compgen -A hostname -- "$cur"))
            return
        }
        #echo bcli complete "$cword" \\"$prev\\" \\"$cur\\" \\"${words[@]}\\"
        COMPREPLY+=($(bcli complete \"$cword\" \"$prev\" \"$cur\" "${words[@]}"))
    }
    complete -o default -F _pybcli_completion bcli pybcli ./pybcli.py pybcli.py
    """
    if system_wide:
        completion_dir = "/etc/bash_completion.d"
    else:
        completion_dir = os.path.expanduser("~/.local/share/bash-completion/completions")

    completion_file = os.path.join(completion_dir, "pybcli")
    print(f"Creating directory {completion_dir} if it does not exist...")
    os.makedirs(completion_dir, exist_ok=True)
    print(f"Writing bash completion script to {completion_file}...")
    with open(completion_file, 'w') as f:
        f.write(bash_completion_script)
        f.close()
    print(f"Bash completion script installed to {completion_file}")

def main():
    pybcli = Pybcli()
    parser = argparse.ArgumentParser(prog='pybcli')
    subparsers = parser.add_subparsers(dest='command')

    # Import subcommand
    import_parser = subparsers.add_parser('import', help='Import a file or directory into a namespace')
    import_parser.add_argument('path', help='The file or directory to import')
    import_parser.add_argument('namespace', nargs='?', help='The namespace to import the file or directory into')

    # Exec subcommand
    exec_parser = subparsers.add_parser('exec', help='Execute a function from a file in a namespace')

    exec_parser.add_argument('--ssh', help='Execute the function over SSH')
    exec_parser.add_argument('namespace', help='The namespace of the file')
    exec_parser.add_argument('file', help='The file containing the function')
    exec_parser.add_argument('func', help='The function to execute')
    exec_parser.add_argument('args', nargs=argparse.REMAINDER, help='Arguments for the function')

    # Info subcommand
    info_parser = subparsers.add_parser('info', help='Display configuration information')
    info_parser.add_argument('-v', '--verbose', action='count', default=0, help='Increase verbosity level')
    info_parser.add_argument('namespace', nargs='?', help='The namespace of the file')
    info_parser.add_argument('file', nargs='?', help='The file containing the function')
    info_parser.add_argument('func', nargs='?', help='The function to execute')

    # Purge subcommand
    subparsers.add_parser('purge', help='Purge non-existing files from metadata')

    # Remove subcommand
    remove_parser = subparsers.add_parser('remove', help='Remove a namespace or a specific file within a namespace')
    remove_parser.add_argument('namespace', help='The namespace to remove')
    remove_parser.add_argument('file', nargs='?', help='The file to remove within the namespace')

    # Complete subcommand for custom bash completion
    complete_parser = subparsers.add_parser('complete', help='Provide bash completion')
    complete_parser.add_argument('comp_cword', type=int, help='COMP_CWORD')
    complete_parser.add_argument('prev', help='Previous word')
    complete_parser.add_argument('curr', help='Current word')
    complete_parser.add_argument('comp_words',  nargs=argparse.REMAINDER, help='COMP_WORDS')

    # Install completion script subcommand
    subparsers.add_parser('install-bash-completion', help='Install bash completion script')

    # Enable bash completion
    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if args.command == 'import':
        location = 'home'
        if args.namespace and '.' in args.namespace:
            location = args.namespace.split('.')[0]
            args.namespace = args.namespace.split('.')[1]
        print(f"location: {location}, namespace: {args.namespace}")
        pybcli.handle_import(args.path, location, args.namespace)
    elif args.command == 'exec':
        pybcli.handle_exec(args.ssh, args.namespace, args.file, args.func, *args.args)
    elif args.command == 'info':
        pybcli.handle_info(args.verbose, args.namespace, args.file, args.func)
    elif args.command == 'purge':
        pybcli.handle_purge()
    elif args.command == 'remove':
        pybcli.handle_remove(args.namespace, args.file)
    elif args.command == 'complete':
        completions = arg_complete(args.comp_cword, args.prev, args.curr, args.comp_words)
        for completion in completions:
            print(completion)
    elif args.command == 'install-bash-completion':
        system_wide = os.geteuid() == 0  # Check if running as root
        install_bash_completion(system_wide)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
