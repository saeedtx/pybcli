#!/bin/bash

SOME_VAR="Hello"
#bcli: export SOME_VAR

#bcli:func description ping something
#bcli:func args "hostname" -c <count> -i <interval> -w <timeout> ..
ping_do() {
    echo run the ping $*
    ping $* &
}

#bcli:func description say hello
#nothing here
#bcli:func args "<something>"
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
