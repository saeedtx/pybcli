#!/usr/bin/env python3
import argparse
import subprocess
import os
import yaml

class Pybcli:
    def __init__(self, home_dir=None, sys_dir=None):
        self.home_dir = home_dir or os.path.expanduser("~/.pybcli")
        self.sys_dir = sys_dir or "/etc/pybcli"

    def set_config_dirs(self, home_dir, sys_dir):
        self.home_dir = home_dir
        self.sys_dir = sys_dir

    def handle_import(self, file, location, namespace):
        # Determine the base directory based on location
        base_dir = self.sys_dir if location == "sys" else self.home_dir
        namespace_dir = os.path.join(base_dir, namespace)
        os.makedirs(namespace_dir, exist_ok=True)

        # Copy the file into the namespace directory
        #target_path = os.path.join(namespace_dir, os.path.basename(file))
        #with open(file, 'r') as src_file:
        #    with open(target_path, 'w') as dest_file:
        #        dest_file.write(src_file.read())

        # Update metadata
        metadata_file = os.path.join(base_dir, "metadata.yaml")
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

    def handle_exec(self, namespace, fname, func, *args):
        # Use default namespace if not provided
        namespace = namespace or "default"

        # Load metadata from home and sys directories
        home_metadata_file = os.path.join(self.home_dir, "metadata.yaml")
        sys_metadata_file = os.path.join(self.sys_dir, "metadata.yaml")

        metadata = {}

        # Load home metadata first
        if os.path.exists(home_metadata_file):
            with open(home_metadata_file, 'r') as mf:
                home_metadata = yaml.safe_load(mf) or {}
                metadata.update(home_metadata)

        # Load sys metadata and merge it
        if os.path.exists(sys_metadata_file):
            with open(sys_metadata_file, 'r') as mf:
                sys_metadata = yaml.safe_load(mf) or {}
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

    def handle_info(self):
        # Print the contents of the config YAML files for both home and sys
        for config_dir, name in [(self.home_dir, 'home'), (self.sys_dir, 'sys')]:
            metadata_file = os.path.join(config_dir, "metadata.yaml")
            print(f"--- {name.upper()} CONFIG ---")
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as mf:
                    metadata = yaml.safe_load(mf) or {}
                    print(yaml.dump(metadata, default_flow_style=False))
            else:
                print("No metadata found.")


def main():
    pybcli = Pybcli()
    parser = argparse.ArgumentParser(prog='pybcli')
    subparsers = parser.add_subparsers(dest='command')

    # Import subcommand
    import_parser = subparsers.add_parser('import', help='Import a file into a namespace')
    import_parser.add_argument('file', help='The file to import')
    import_parser.add_argument('location', choices=['home', 'sys'], default='home', nargs='?', help='The location to import the file (home or system)')
    import_parser.add_argument('namespace', nargs='?', default='default', help='The namespace to import the file into')

    # Exec subcommand
    exec_parser = subparsers.add_parser('exec', help='Execute a function from a file in a namespace')
    exec_parser.add_argument('namespace', help='The namespace of the file')
    exec_parser.add_argument('file', help='The file containing the function')
    exec_parser.add_argument('func', help='The function to execute')
    exec_parser.add_argument('args', nargs=argparse.REMAINDER, help='Arguments for the function')

    # Info subcommand
    info_parser = subparsers.add_parser('info', help='Display configuration information')

    args = parser.parse_args()

    if args.command == 'import':
        pybcli.handle_import(args.file, args.location, args.namespace)
    elif args.command == 'exec':
        pybcli.handle_exec(args.namespace, args.file, args.func, *args.args)
    elif args.command == 'info':
        pybcli.handle_info()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
