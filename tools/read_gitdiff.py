#!/usr/bin/env python3
# -*- coding: utf-8 -*-
################################################################################

import argparse

################################################################################
class Project:

    def __init__(self):
        self.diffFileName = ''
        self.changes = {}


    @staticmethod
    def readFileToList(filePath):
        theFile = open(filePath, 'r')
        fileContent = []
        for line in theFile:
            fileContent.append(line.rstrip(' \t\n\r').lstrip(' \t'))
        theFile.close()
        return(fileContent)


    @staticmethod
    def parseLineNumbers(line):
        data = line.split(' ')
        addInfo = data[2][1:]
        numSep = ','
        if numSep in addInfo:
            addData = addInfo.split(numSep)
            start = int(addData[0])
            count = int(addData[1])
        else:
            start = int(addInfo)
            count = 1
        return(start, count)


    def readGitDiffFile(self, fileName):
        self.diffFileName = fileName
        fileContent = Project.readFileToList(self.diffFileName)
        srcPath = ''
        linesList = []
        for aLine in fileContent:
            if aLine[0:6] == '+++ b/':
                # store the previous results if any
                if len(srcPath) > 0 and len(linesList) > 0:
                    self.changes[srcPath] = linesList
                # get the file name
                srcPath = aLine[6:]
                linesList = []
            elif aLine[0:2] == '@@':
                addStart, addCount = Project.parseLineNumbers(aLine)
                if addCount > 0:
                    linesList.append(addStart)
        # don't forget the last file
        if len(srcPath) > 0 and len(linesList) > 0:
            self.changes[srcPath] = linesList


    def printChanges(self):
        print(self.changes)



################################################################################
if __name__ == '__main__':
    myParser = argparse.ArgumentParser(description="Read a file that contains the result of a git diff command with the -U0 option, e.g. 'git diff -U0 <commit_sha1> <commit_sha_2>'; Then print the file names and their modified lines.")
    myParser.add_argument('file_name',
       help = 'Name of the file to read')
    myArgs = myParser.parse_args()

    myProject = Project()
    myProject.readGitDiffFile(myArgs.file_name)
    myProject.printChanges()
