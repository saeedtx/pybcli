

#bcli:func description This is out_put_test
#bcli:func args "arg1 arg2..."
out_put_test() {
    echo "Line1: This is a test"
    echo "Line2: $*"
}