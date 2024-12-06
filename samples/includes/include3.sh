#!/bin/bash

. includes/include4.sh

i_am_from_include3() {
    echo "I am from include3: called from $1"
    echo "calling i_am_from_include4"
    pwd
    i_am_from_include4 $1
}
