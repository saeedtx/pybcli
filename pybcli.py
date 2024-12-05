#!/usr/bin/env python3
import argparse
import subprocess
import os


def handle_import(file, namespace):
    # Logic for importing a file into a specific namespace (or default namespace)
    print(f"Importing file '{file}' into namespace '{namespace}'")


def handle_exec(namespace, file, func, *args):
    # Logic for executing a function from a file within a namespace
    print(f"Executing '{func}' from file '{file}' in namespace '{namespace}' with arguments {args}")
    # Placeholder logic to simulate SSH command execution
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

    args = parser.parse_args()

    if args.command == 'import':
        handle_import(args.file, args.namespace)
    elif args.command == 'exec':
        handle_exec(args.namespace, args.file, args.func, *args.args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()