#!/usr/bin/env python3
import unittest
import os
import shutil
import yaml
import tempfile
from pybcli import Pybcli

class TestPybcli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create temporary directories for testing
        cls.temp_home_dir = tempfile.mkdtemp()
        cls.temp_sys_dir = tempfile.mkdtemp()

        # Initialize Pybcli instance and configure it to use the temporary directories
        cls.pybcli = Pybcli()
        cls.pybcli.set_config_dirs(cls.temp_home_dir, cls.temp_sys_dir)

    @classmethod
    def tearDownClass(cls):
        # Cleanup the temporary directories after tests
        shutil.rmtree(cls.temp_home_dir)
        shutil.rmtree(cls.temp_sys_dir)

    def test_import_home_default_namespace(self):
        # Test importing a file into the home location with default namespace
        test_file = "samples/pinger.sh"

        try:
            self.pybcli.handle_import(test_file, "home", "default")
            self.assertTrue(os.path.exists(self.pybcli.home_dir))

            # Check metadata
            metadata_file = os.path.join(self.pybcli.home_dir, "metadata.yaml")
            with open(metadata_file, "r") as mf:
                metadata = yaml.safe_load(mf)
                self.assertIsInstance(metadata, dict)
                namespace = "default"
                self.assertIn(namespace, metadata)
                fname = os.path.splitext(os.path.basename(test_file))[0]
                self.assertIn(fname, metadata[namespace])
                self.assertEqual(metadata[namespace][fname], os.path.abspath(test_file))
        finally:
            pass

    def test_import_sys_custom_namespace(self):
        # Test importing a file into the sys location with a custom namespace
        test_file = "samples/info.sh"
        namespace = "custom_namespace"

        try:
            self.pybcli.handle_import(test_file, "sys", namespace)
            self.assertTrue(os.path.exists(self.pybcli.sys_dir))

            # Check metadata
            metadata_file = os.path.join(self.pybcli.sys_dir, "metadata.yaml")
            with open(metadata_file, "r") as mf:
                metadata = yaml.safe_load(mf)
                self.assertIsInstance(metadata, dict)
                self.assertIn(namespace, metadata)
                fname = os.path.splitext(os.path.basename(test_file))[0]
                self.assertIn(fname, metadata[namespace])
                self.assertEqual(metadata[namespace][fname], os.path.abspath(test_file))
        finally:
            pass

    def test_exec_function(self):
        # Test executing a function from a file
        test_file = "samples/pinger.sh"
        func_name = "ping_test"
        namespace = "default"
        fname = os.path.splitext(os.path.basename(test_file))[0]

        try:
            self.pybcli.handle_import(test_file, "home", namespace)
            self.pybcli.handle_exec(namespace, fname, func_name, "localhost -c 2")
        finally:
            pass

    def test_output_function(self):
        # Test executing a function that outputs multiple lines
        test_file = "samples/output.sh"
        func_name = "out_put_test"
        namespace = "default"
        fname = os.path.splitext(os.path.basename(test_file))[0]

        try:
            self.pybcli.handle_import(test_file, "home", namespace)
            with tempfile.TemporaryFile(mode='w+') as temp_output:
                # Redirect stdout to capture the function output
                original_stdout = os.dup(1)
                os.dup2(temp_output.fileno(), 1)

                # Execute the function
                self.pybcli.handle_exec(namespace, fname, func_name, "This is a parameter")

                # Reset stdout
                os.dup2(original_stdout, 1)
                os.close(original_stdout)

                # Read and verify output
                temp_output.seek(0)
                output = temp_output.read()
                self.assertIn("Line1: This is a test", output)
                self.assertIn("Line2: This is a parameter", output)
        finally:
            pass

if __name__ == "__main__":
    unittest.main()
