# Pybcli

Pybcli is a command-line tool for managing and executing Bash functions, it supports neat autocompletion and seamless
execution of functions over SSH without the need to manually copy the script to the remote server.

Long gone the days of forgetting where you put that one bash function that you need to run on a remote server.

## Key Features

- Import a bash file (with functions) or directory into a namespace
- Execute a function from a file within a namespace
- **Execute a function from a file within a namespace over SSH**
- Auto-completion for bash functions and namespaces
- File management (display, purge, remove)

## Installation

To install Pybcli, clone the repository and install the dependencies:

```sh
git clone https://github.com/saeedtx/pybcli.git
cd pybcli
pip install -r requirements.txt
bcli install-bash-completion
```

## Usage

### Import a file or directory into a namespace

```sh
# Import a single file into the default namespace
bcli import /path/to/your/script.sh

# Import a single file into a custom namespace
bcli import /path/to/your/script.sh custom_namespace

# Import a directory into the default namespace
bcli import /path/to/your/scripts

# Import a directory into a custom namespace
bcli import /path/to/your/scripts custom_namespace
```

### Execute a function from a file in a namespace

```sh
# Execute a function locally
bcli exec namespace script_name function_name arg1 arg2

# **Execute a function over SSH**
bcli exec --ssh user@remote_host namespace script_name function_name arg1 arg2
```

### Display configuration information

```sh
# Display configuration information with default verbosity
bcli info

# Display configuration information with increased verbosity
bcli info -v
bcli info -vv
bcli info -vvv
```

### Purge non-existing files from metadata

```sh
bcli purge
```

### Remove a namespace or a specific file within a namespace

```sh
# Remove an entire namespace
bcli remove custom_namespace

# Remove a specific file within a namespace
bcli remove custom_namespace script_name
```

### Install bash completion script

```sh
# Install system-wide (requires root)
sudo bcli install-bash-completion

# Install for the current user
bcli install-bash-completion
```

## Examples

### Importing and Executing Scripts

1. Import a script into the default namespace:

	```sh
	bcli import /home/user/scripts/my_script.sh
	```

2. Execute a function from the imported script:

	```sh
	bcli exec default my_script my_function arg1 arg2
	```

3. Import a directory of scripts into a custom namespace:

	```sh
	bcli import /home/user/scripts custom_namespace
	```

4. Execute a function from a script in the custom namespace:

	```sh
	bcli exec custom_namespace my_script my_function arg1 arg2
	```

### Managing Metadata

1. Display configuration information:

	```sh
	bcli info
	```

2. Purge non-existing files from metadata:

	```sh
	bcli purge
	```

3. Remove a namespace:

	```sh
	bcli remove custom_namespace
	```

4. Remove a specific file within a namespace:

	```sh
	bcli remove custom_namespace my_script
	```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
