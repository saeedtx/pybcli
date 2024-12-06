. ./simple.sh;set -e
source ./moderate.sh

#bcli:func description This is out_put_test
#bcli:func args "arg1 arg2..."
run_test() {
    echo "This is includes test"
    echo "Args: $@"
    echo "Running function1 $1"
    function1 $1
    echo "Running function2"
    function2 $1 $2
    echo "Running i_shall_pass"
    i_shall_pass $1
    echo
}