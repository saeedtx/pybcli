#!/bin/bash
. include1.sh
. includes/include2.sh
. includes/include3.sh


test_includes()
{
	echo "This is multi includes test"
	i_am_from_include1 test_includes
	i_am_from_include2 test_includes
}

test_multi_level_includes()
{
	echo "This is multi level includes test"
	i_am_from_include3 test_multi_level_includes
}
