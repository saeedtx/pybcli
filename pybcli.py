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
        target_path = os.path.join(namespace_dir, os.path.basename(file))
        with open(file, 'r') as src_file:
            with open(target_path, 'w') as dest_file:
                dest_file.write(src_file.read())
        print(f"File '{file}' has been successfully imported into namespace '{namespace}' at '{target_path}'")

        # Update metadata
        metadata_file = os.path.join(base_dir, "metadata.yaml")
        metadata = {}
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as mf:
                metadata = yaml.safe_load(mf) or {}

        if namespace not in metadata:
            metadata[namespace] = []
        if os.path.basename(file) not in metadata[namespace]:
            metadata[namespace].append(os.path.basename(file))

        with open(metadata_file, 'w') as mf:
            yaml.safe_dump(metadata, mf)
        print(f"Metadata updated for namespace '{namespace}' at '{metadata_file}'")

    def handle_exec(self, namespace, file, func, *args):
        # Logic for executing a function from a file within a namespace
        print(f"Executing '{func}' from file '{file}' in namespace '{namespace}' with arguments {args}")
        remote_command = f"source {file} && {func} {' '.join(args)}"
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

    args = parser.parse_args()

    if args.command == 'import':
        pybcli.handle_import(args.file, args.location, args.namespace)
    elif args.command == 'exec':
        pybcli.handle_exec(args.namespace, args.file, args.func, *args.args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
