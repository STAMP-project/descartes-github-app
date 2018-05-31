#!/bin/sh
################################################################################

fileName="$1"
prettyFile=$fileName".pretty"

cat $fileName | python -m json.tool > $prettyFile
vi $prettyFile

