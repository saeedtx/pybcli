#!/bin/bash

#bcli: description This is function1
function1() {
    echo "function1 here $1"
}

#bcli: description This is function2
function2() {
    echo "function2 here $1 $2"
}

main() {
    echo Args: $@
    echo "Running function1 $1"
    function1 $1
    echo "Running function2"
    function2 $1 $2
}


forward_args()
{
    echo "Forwarding args to main"
    main $@
}

args_test() {
    echo "Running args_test"
    echo "Args: $@"
    echo "Args: $1 $2"
    forward_args $@
}