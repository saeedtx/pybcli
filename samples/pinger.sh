#!/bin/bash

SOME_VAR="Hello"
#bcli: description This is function_a
#bcli: export SOME_VAR
ping_do() {
    echo run the ping $*
    ping $* &
}

#bcli: description This is function_b
say_hello() {
    for i in {1..3}; do
	echo hello $i
	sleep 1
    done &
}

ping_test() {
    ping_do $@
    say_hello $@
}
