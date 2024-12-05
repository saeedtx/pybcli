#!/usr/bin/env python3
import argparse
import subprocess
import os
import yaml
import argcomplete  # Add import for argcomplete
import re

class Pybcli:
    def __init__(self, home_dir=None, sys_dir=None):
        self.home_dir = home_dir or os.path.expanduser("~/.pybcli")
        self.sys_dir = sys_dir or "/etc/pybcli"
        self.home_metadata_file = os.path.join(self.home_dir, "metadata.yaml")
        self.sys_metadata_file = os.path.join(self.sys_dir, "metadata.yaml")

    def handle_import(self, file, location, namespace):
        # Determine the base directory based on location
        base_dir = self.sys_dir if location == "sys" else self.home_dir
        namespace_dir = os.path.join(base_dir, namespace)
        os.makedirs(namespace_dir, exist_ok=True)

        # Update metadata
        metadata_file = self.sys_metadata_file if location == "sys" else self.home_metadata_file
        metadata = {}
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as mf:
                metadata = yaml.safe_load(mf) or {}

        if namespace not in metadata:
            metadata[namespace] = {}
        fname = os.path.splitext(os.path.basename(file))[0]
        metadata[namespace][fname] = os.path.abspath(file)
        print(f"File '{os.path.abspath(file)}' has been successfully imported into namespace '{namespace}/{fname}'")

        with open(metadata_file, 'w') as mf:
            yaml.safe_dump(metadata, mf)
        print(f"Metadata updated for namespace '{namespace}' at '{metadata_file}'")

    def load_metadata(self, is_sys = False):
        metadata_file = self.sys_metadata_file if is_sys else self.home_metadata_file
        metadata = {}
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as mf:
                metadata = yaml.safe_load(mf) or {}
        return metadata

    def handle_exec(self, namespace, fname, func, *args):
        # Use default namespace if not provided
        namespace = namespace or "default"

        # Load metadata from home and sys directories
        metadata = self.load_metadata(is_sys=False) # home metadata
        sys_metadata = self.load_metadata(is_sys=True) # sys metadata

        # Load sys metadata and merge it with home metadata
        for ns, files in sys_metadata.items():
            if ns in metadata:
                metadata[ns].update(files)
            else:
                metadata[ns] = files

        if namespace not in metadata or fname not in metadata[namespace]:
            raise FileNotFoundError(f"File '{fname}' not found in namespace '{namespace}'")

        # Get the full path of the file
        file_path = metadata[namespace][fname]

        # Execute the function from the file
        print(f"Executing '{func}' from file '{file_path}' in namespace '{namespace}' with arguments {args}")
        remote_command = f"source {file_path} && {func} {' '.join(args)}"
        print(f"Executing command: {remote_command}")
        process = subprocess.Popen(["bash", "-c", remote_command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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
        home_meta = os.path.join(os.path.expanduser("~/.pybcli"), "metadata.yaml")
        sys_meta = os.path.join("/etc/pybcli", "metadata.yaml")
        home_metadata = {}
        if os.path.exists(home_meta):
            with open(home_meta, 'r') as mf:
                home_metadata = yaml.safe_load(mf) or {}
        home_namespaces = list(home_metadata.keys())
        options = [f"home.{ns}" for ns in home_namespaces]

        sys_metadata = {}
        if os.path.exists(sys_meta):
            with open(sys_meta, 'r') as mf:
                sys_metadata = yaml.safe_load(mf) or {}

        sys_namespaces = list(sys_metadata.keys())
        # add sys. prefix to sys namespaces
        options += [f"sys.{ns}" for ns in sys_namespaces]
        for ns in home_namespaces + sys_namespaces:
                return [f for f in options if f.startswith(curr)]


def main():
    pybcli = Pybcli()
    parser = argparse.ArgumentParser(prog='pybcli')
    subparsers = parser.add_subparsers(dest='command')

    # Import subcommand
    import_parser = subparsers.add_parser('import', help='Import a file into a namespace')
    import_parser.add_argument('file', help='The file to import')
    import_parser.add_argument('namespace', nargs='?', default='default', help='The namespace to import the file into')

    # Exec subcommand
    exec_parser = subparsers.add_parser('exec', help='Execute a function from a file in a namespace')
    exec_parser.add_argument('namespace', help='The namespace of the file')
    exec_parser.add_argument('file', help='The file containing the function')
    exec_parser.add_argument('func', help='The function to execute')
    exec_parser.add_argument('args', nargs=argparse.REMAINDER, help='Arguments for the function')

    # Info subcommand
    info_parser = subparsers.add_parser('info', help='Display configuration information')
    info_parser = subparsers.add_parser('write-completion-script', help='Completion script')

    # Complete subcommand for custom bash completion
    complete_parser = subparsers.add_parser('complete', help='Provide bash completion')
    complete_parser.add_argument('comp_cword', type=int, help='COMP_CWORD')
    complete_parser.add_argument('prev', help='Previous word')
    complete_parser.add_argument('curr', help='Current word')
    complete_parser.add_argument('comp_words', nargs=argparse.REMAINDER, help='COMP_WORDS')

    # Enable bash completion
    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if args.command == 'import':
        location = 'home'
        if '.' in args.namespace:
            location = args.namespace.split('.')[0]
            args.namespace = args.namespace.split('.')[1]
        print(f"location: {location}, namespace: {args.namespace}")
        pybcli.handle_import(args.file, location, args.namespace)
    elif args.command == 'exec':
        pybcli.handle_exec(args.namespace, args.file, args.func, *args.args)
    elif args.command == 'info':
        pybcli.handle_info()
    elif args.command == 'complete':
        completions = arg_complete(args.comp_cword, args.prev, args.curr, args.comp_words)
        for completion in completions:
            print(completion)
    elif args.command == 'write-completion-script':
        dump_completion_script()
    else:
        parser.print_help()

def dump_completion_script():
    import os
    bash_completion_script = """
    _pybcli_completion() {
        local cur prev words cword
        _get_comp_words_by_ref -n : cur prev words cword
        # return files if import
        [[ $cword -eq 2 ]] && [ "$prev" == "import" ] && {
            COMPREPLY=($(compgen -- "$cur"))
            return
        }
        COMPREPLY=($(pybcli complete \"$cword\" \"$prev\" \"$cur\" "${words[@]}"))
    }
    complete -o default -F _pybcli_completion pybcli ./pybcli.py pybcli.py
    """
    print(f"{bash_completion_script}")

if __name__ == "__main__":
    main()
