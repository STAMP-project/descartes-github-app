#!/usr/bin/env python3

import sys
import pathlib
import datetime
from github3 import login

myFile = pathlib.Path.home().joinpath('.github_token').open()
myToken = myFile.readline()[:-1]

# print(myToken)

githubLogin = login(token=myToken)
repo = githubLogin.repository('STAMP-project', 'experiments')

prName = 'myPR_' + str(datetime.datetime.now())
pullRequest = repo.create_pull(prName, 'master', 'STAMP-project:branchForTest', 'foo')

sys.exit(1 if not pullRequest else 0)
