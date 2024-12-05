#!/bin/bash

#bcli: description This is function1
i_shall_pass() {
    echo "I shall pass with $1"
    true
}

#bcli: description This is function2
i_shall_fail() {
    set -e
    echo "I shall fail with $1"
    false
    return $1
}

i_shall_not_run() {
    echo "I shall not run"
    false
}

run_test() {
    set -e
    echo Args: $@
    echo "Running i_shall_pass"
    i_shall_pass $1
    echo "Running i_shall_fail"
    i_shall_fail $1
    i_shall_not_run
}
