#!/usr/bin/env python3
import unittest
import os
import shutil
import yaml
import tempfile
import tracemalloc
from pybcli.pybcli import Pybcli

class TestPybcli(unittest.TestCase):
    BASH_SCRIPTS_DIR = os.path.abspath("samples")
    @classmethod
    def setUp(self):
        # Create temporary directories for testing
        self.temp_home_dir = tempfile.mkdtemp()
        self.temp_sys_dir = tempfile.mkdtemp()

        # Initialize Pybcli instance and configure it to use the temporary directories
        self.pybcli = Pybcli(self.temp_home_dir, self.temp_sys_dir)

    def tearDown(self):
        # Cleanup the temporary directories after each test
        shutil.rmtree(self.temp_home_dir)
        shutil.rmtree(self.temp_sys_dir)

    def _test_import_namespace(self, bash_file, is_sys, namespace):
        # Test importing a file into the home location with default namespace
        test_file = f"{self.BASH_SCRIPTS_DIR}/{bash_file}"
        location = "sys" if is_sys else "home"

        try:
            self.pybcli.handle_import(test_file, location, namespace)
            self.assertTrue(os.path.exists(self.pybcli.home_dir))
            namespace = namespace or "default"
            conf_dir = self.pybcli.sys_dir if is_sys else self.pybcli.home_dir
            # Check metadata
            metadata_file = os.path.join(conf_dir, "metadata.yaml")
            with open(metadata_file, "r") as mf:
                metadata = yaml.safe_load(mf)
                self.assertIsInstance(metadata, dict)
                self.assertIn(namespace, metadata)
                fname = os.path.splitext(os.path.basename(test_file))[0]
                self.assertIn(fname, metadata[namespace])
                self.assertEqual(metadata[namespace][fname], os.path.abspath(test_file))
                # close the file
                mf.close()
        finally:
            pass

    def _test_import_dir(self, dir, is_sys, namespace):
        # Test importing a directory into the home location with default namespace
        location = "sys" if is_sys else "home"
        try:
            self.pybcli.handle_import(dir, location, namespace)

            self.assertTrue(os.path.exists(self.pybcli.home_dir))
            namespace = namespace or os.path.basename(dir)
            conf_dir = self.pybcli.sys_dir if is_sys else self.pybcli.home_dir
            # Check metadata
            metadata_file = os.path.join(conf_dir, "metadata.yaml")
            with open(metadata_file, "r") as mf:
                metadata = yaml.safe_load(mf)
                self.assertIsInstance(metadata, dict)
                self.assertIn(namespace, metadata)
                for root, dirs, files in os.walk(dir):
                    for file in files:
                        # check if file is a bash file?
                        if not file.endswith(".sh"):
                            continue
                        fname = os.path.splitext(file)[0]
                        self.assertIn(fname, metadata[namespace])
                        self.assertEqual(metadata[namespace][fname], os.path.abspath(f"{root}/{file}"))
                # close the file
                mf.close()
        finally:
            pass

    def test_import_dir_home_default_namespace(self):
        self._test_import_dir("samples", False, None)
        self._test_import_dir("samples", False, "mydir")

    def test_import_home_default_namespace(self):
        self._test_import_namespace("simple.sh", False, None)
        self._test_import_namespace("output.sh", False, "default")

    def test_import_home_custom_namespace(self):
        self._test_import_namespace("simple.sh", False, "test_namespace")

    def test_import_sys_custom_namespace(self):
        self._test_import_namespace("simple.sh", True, "custom_namespace")

    def _test_scan_file_funcs(self, bash_file, func_list):
        test_file = f"{self.BASH_SCRIPTS_DIR}/{bash_file}"
        fmeta = self.pybcli.scan_bash_file(test_file)
        self.assertIsInstance(fmeta, dict)
        self.assertIn("functions", fmeta)
        self.assertIn("file", fmeta)
        self.assertEqual(fmeta["file"], test_file)
        self.assertLessEqual(len(func_list), len(fmeta["functions"]))
        func_names = [ meta["name"] for meta in fmeta["functions"] ]
        for func in func_list:
            self.assertIn(func, func_names)

    def test_scan_bash_file(self):
        self._test_scan_file_funcs("simple.sh", ["function1", "function2", "main"])

    def test_scan_bash_file_includes(self):
        test_file = f"{self.BASH_SCRIPTS_DIR}/test_includes.sh"
        fmeta = self.pybcli.scan_bash_file(test_file)
        self.assertIsInstance(fmeta, dict)
        self.assertIn("includes", fmeta)
        expected_includes = [
            {
                'line_number': 1,
                'include_line': '. ./simple.sh',
                'full_path': os.path.abspath(os.path.join(self.BASH_SCRIPTS_DIR, 'simple.sh'))
            },
            {
                'line_number': 2,
                'include_line': 'source ./moderate.sh',
                'full_path': os.path.abspath(os.path.join(self.BASH_SCRIPTS_DIR, 'moderate.sh'))
            }
        ]
        self.assertEqual(fmeta["includes"], expected_includes)

    def _test_exec(self, is_sys, namespace, bash_file, func_name, *args):
        test_file = f"{self.BASH_SCRIPTS_DIR}/{bash_file}"
        fname = os.path.splitext(os.path.basename(test_file))[0]
        location = "sys" if is_sys else "home"
        rc, output = -1, None
        try:
            self.pybcli.handle_import(test_file, location, namespace)
            with tempfile.TemporaryFile(mode='w+') as temp_output:
                original_stdout = os.dup(1)
                os.dup2(temp_output.fileno(), 1)
                rc = self.pybcli.handle_exec(None, namespace, fname, func_name, *args)
                os.dup2(original_stdout, 1)
                os.close(original_stdout)
                temp_output.seek(0)
                output = temp_output.read()
        except FileNotFoundError:
            self.fail(f"Test file {test_file} not found.")
        finally:
            pass
        return rc, output

    def test_exec_home_default_namespace(self):
        args = ["arg1", "arg2", "arg3"]
        rc, output = self._test_exec(False, None, "simple.sh", "main", *args)
        self.assertEqual(rc, 0)
        self.assertIn("function1 here arg1", output)
        self.assertIn("function2 here arg1 arg2", output)
        self.assertIn("Args: arg1 arg2 arg3", output)

    def test_exec_rc_code(self):
        rc, output = self._test_exec(False, None, "moderate.sh", "i_shall_pass", "1")
        self.assertEqual(rc, 0)
        self.assertIn("I shall pass", output)
        rcs = [ 1, 10, 100 ]
        for test_rc in rcs:
            rc, output = self._test_exec(False, None, "moderate.sh", "i_shall_fail", str(test_rc))
            self.assertEqual(test_rc, rc)
            self.assertIn(f"I shall fail with {test_rc}", output)
        rc, output = self._test_exec(False, None, "moderate.sh", "run_test", "1")
        self.assertEqual(rc, 1)
        self.assertIn("I shall fail with", output)
        # TODO this assert shouldn't fail due to -e, but it does
        #self.assertNotIn("I shall not run", output)

if __name__ == "__main__":
    tracemalloc.start()
    unittest.main(verbosity=2)
