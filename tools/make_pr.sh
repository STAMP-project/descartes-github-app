#!/bin/sh
################################################################################

fileName="README.md"
templateName="README.template"

if git checkout branchForTest
then
   cp $templateName $fileName
   Date=`date`
   echo $Date >> $fileName

   if git commit -a -m "$Date"
   then
      if git push
      then
         git checkout master
         make_pr.py
      fi
   fi
fi
