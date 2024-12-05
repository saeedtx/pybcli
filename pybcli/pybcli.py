#!/usr/bin/env python3
import argparse
import subprocess
import os
import yaml
import argcomplete  # Add import for argcomplete
import re
import tempfile

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

    def resolve_file(self, namespace, fname):
        metadata = self.load_all_metadata()
        if namespace not in metadata or fname not in metadata[namespace]:
            raise FileNotFoundError(f"File '{fname}' not found in namespace '{namespace}'")
        return metadata[namespace][fname]

    def bash_popen(self, file, func, *args):
        # Execute the function from the file
        print(f"Executing '{file}'->'{func}' {args}")
        command = f"source {file} && {func} {' '.join(args)} && wait"
        print(f"Executing command: {command}")
        return subprocess.Popen(["bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def ssh_popen(self, remote, file, func, *args):
        # Open a persistent SSH connection using ControlMaster
        fname = os.path.splitext(os.path.basename(file))[0]
        ssh_control_path = tempfile.mktemp(prefix=f"bcli_ssh_control_{fname}_{func}_{remote.replace('@', '_')}-")
        ssh_command = [
            "ssh", "-MNf", "-o", f"ControlPath={ssh_control_path}", "-o", "ControlMaster=yes", remote
        ]
        print(f"Opening persistent SSH connection to {remote}: {ssh_control_path}...")
        subprocess.run(ssh_command, check=True)

        # Send the bash file using SCP via the persistent connection
        remote_file = os.path.basename(file)
        scp_command = [
            "scp", "-o", f"ControlPath={ssh_control_path}", file, f"{remote}:{remote_file}"
        ]
        print(f"Transferring {file} to {remote}...")
        subprocess.run(scp_command, check=True)

        # Execute the function via the persistent SSH connection
        remote_command = f"bash -c 'source {remote_file} && {func} {' '.join(args)}' && wait"
        exec_command = [
            "ssh", "-o", f"ControlPath={ssh_control_path}", remote, remote_command
        ]
        print(f"Executing command: {remote_command}")
        process = subprocess.Popen(exec_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        process.ssh_control_path__ = ssh_control_path
        return process

    def handle_exec(self, remote, namespace, fname, func, *args):
        namespace = namespace or "default"
        file = self.resolve_file(namespace, fname)
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
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    print(output, end="")

            # Print any remaining errors
            stderr = process.stderr.read()
            if stderr:
                print("--- STDERR ---")
                print(stderr)
            rc = process.poll()
            print(f"Command execution complete with return code: {rc}")
        except subprocess.CalledProcessError as e:
            print(f"Command error: {e}")
        except FileNotFoundError:
            print(f"Error: File {file} not found")
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
                print("Closing persistent SSH connection...")
                subprocess.run(close_command, check=False)
        return rc

    def scan_bash_file(self, file_path):
        # Scan a bash file and extract metadata
        if not os.path.exists(file_path):
            print("\nFile doesn't exist. Please run bcli2 purge.")
            return None

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
        # TODO: dict ?
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

        file_metadata = {
            'file': file_path,
            'global_annotations': global_annotations,
            'functions': functions
        }

        return file_metadata

    def handle_info(self):
        # Print the contents of the config YAML files for both home and sys
        for name in ['home', 'sys']:
            metadata = self.load_metadata(is_sys=(name == 'sys'))
            print(f"--- {name.upper()} CONFIG ---")
            #print(yaml.dump(metadata, default_flow_style=False))
            for ns, files in metadata.items():
                print(f"Namespace: {ns}")
                for fname, fpath in files.items():
                    print(f"  {fname}: {fpath}")
                    file_metadata = self.scan_bash_file(fpath)
                    if not file_metadata:
                        continue
                    for func in file_metadata['functions']:
                        description = func['annotations'].get('description') or ""
                        print(f"    - {func['name'] : <25} {description}")

def arg_complete(comp_cword, prev, curr, comp_words):
    if comp_cword == 1:
        options = ["import", "exec", "info"]
        return [f for f in options if f.startswith(curr)]

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
    elif cmd == 'exec':
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
        COMPREPLY+=($(pybcli complete \"$cword\" \"$prev\" \"$cur\" "${words[@]}"))
    }
    complete -o default -F _pybcli_completion pybcli ./pybcli.py pybcli.py
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
    subparsers.add_parser('info', help='Display configuration information')

    # Complete subcommand for custom bash completion
    complete_parser = subparsers.add_parser('complete', help='Provide bash completion')
    complete_parser.add_argument('comp_cword', type=int, help='COMP_CWORD')
    complete_parser.add_argument('prev', help='Previous word')
    complete_parser.add_argument('curr', help='Current word')
    complete_parser.add_argument('comp_words', nargs=argparse.REMAINDER, help='COMP_WORDS')

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
        elif not args.namespace:
            args.namespace = os.path.basename(os.path.normpath(args.path))
        print(f"location: {location}, namespace: {args.namespace}")
        pybcli.handle_import(args.path, location, args.namespace)
    elif args.command == 'exec':
        pybcli.handle_exec(args.ssh, args.namespace, args.file, args.func, *args.args)
    elif args.command == 'info':
        pybcli.handle_info()
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
