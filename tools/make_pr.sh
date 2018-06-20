#!/bin/sh
################################################################################

fileName="README.md"
templateName="README.template"

srcDir="src/main/java/eu/stamp_project/examples/dhell"
className="HelloApp.java"
testSrcDir="src/test/java/eu/stamp_project/examples/dhell"
testClassName="HelloAppTest.java"

if git checkout branchForTest
then
   cp $templateName $fileName
   Date=`date`
   echo $Date >> $fileName

   cp $srcDir/$className.new $srcDir/$className
   cp $testSrcDir/$testClassName.new $testSrcDir/$testClassName

   if git commit -a -m "$Date"
   then
      if git push
      then
         git checkout master
         make_pr.py
      fi
   fi
fi
