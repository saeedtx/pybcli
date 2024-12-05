#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name='pybcli',
    version='0.1.0',
    description='CLI tool to manage and execute bash functions locally or over SSH',
    author='Saeed Mahameed <saeed@kernel.org>',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'pybcli=pybcli.cli:main',  # You can change 'pybcli' to the desired executable name later
        ],
    },
)
