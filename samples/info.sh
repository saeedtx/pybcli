#!/bin/bash
set -e

dump_sys_info() {

    echo "Dumping system info"
    echo "-------------------"
    echo "Hostname: $(hostname)"
    echo "Kernel: $(uname -r)"
    echo "Uptime: $(uptime)"
    echo "-------------------"
}

#bcli: description This is function_b
dump_hw_info() {
    echo "Dumping hardware info"
    echo "---------------------"
    echo "CPU: $(lscpu)"
    echo "Memory: $(free -h)"
    echo "---------------------"
}

get_info() {
    set -e
    dump_sys_info
    dump_hw_info
    echo "All done"
}
