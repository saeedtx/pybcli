#!/usr/bin/env python3
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop
import subprocess
import sys
import os

class PostInstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        subprocess.call(['sudo', sys.executable, '-m', 'pybcli', 'install-completion-script'])

class PostDevelopCommand(develop):
    """Post-installation for development mode."""
    def run(self):
        develop.run(self)
        python_executable = sys.executable
        subprocess.call([python_executable, '-m', 'pybcli', 'install-completion-script'])

class PostUninstallCommand(install):
    """Post-uninstallation for uninstallation mode."""
    def run(self):
        install.run(self)
        completion_file = "/etc/bash_completion.d/pybcli"
        if os.path.exists(completion_file):
            os.remove(completion_file)
            print(f"Bash completion script removed from {completion_file}")

setup(
    name='pybcli',
    version='0.1.0',
    description='CLI tool to manage and execute bash functions locally or over SSH',
    author='Saeed Mahameed <saeed@kernel.org>',
    packages=find_packages(include=['pybcli', 'pybcli.*']),
    entry_points={
        'console_scripts': [
            'bcli=pybcli.pybcli:main',  # Correctly reference the main function in pybcli.py
        ],
    },
    cmdclass={
        'install': PostInstallCommand,
        'develop': PostDevelopCommand,
        'uninstall': PostUninstallCommand,
    },
)
