#!/usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################

from flask import Flask, request
import json
import uuid
import requests
import jwt
from Crypto.PublicKey import RSA
import time
import datetime
import sys
import os
import subprocess
import pika
import shutil

from reporting import generate_annotations

GITHUB_API = 'https://api.github.com/'
APP_ID = 12748
CHECK_RUN_STEP_1_NAME = 'Getting repository'
CHECK_RUN_STEP_2_NAME = 'Compiling project'
CHECK_RUN_STEP_3_NAME = 'Looking for pseudo-tested methods'

DEFAULT_QUEUE = 'descartes'

################################################################################
# don't change the variable name 'application' otherwise uwsgi won't work anymore
application = Flask(__name__)

################################################################################
# receiving requests
@application.route('/', methods = ['GET', 'POST'])
def pullrequest_opened():
    payload = Payload(request.json)
    dump(payload.data, 'other')
    if not payload.isPullRequest():
        return 'No pull request event', 400
    dump(payload.data, 'pr')

    # this send the message to the consumer
    # the consumer can be either run manually (workers.py) to debug
    # or run as a service to deploy
    sender = Producer()
    sender.createWork(payload)

    return 'Everything went well :)'


################################################################################
# functions
def success(response):
    # need to be improved
    return(200 <= response.status_code < 300)


def dump(data, prefix = 'dump'):
    unique_filename = prefix + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json'
    with open(unique_filename, 'w') as _file:
        json.dump(data, _file)


def trace(message):
    print("######## " + message, file = sys.stderr)


################################################################################
class Channel:

    def connectRabbitmq(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters \
            (host = 'localhost'))
        channel = connection.channel()
        channel.queue_declare(DEFAULT_QUEUE, durable = True)
        return connection, channel


################################################################################
class Producer(Channel):

    def createWork(self, payload):
        connection, channel = self.connectRabbitmq()
        channel.basic_publish(exchange = '', routing_key = DEFAULT_QUEUE,
            body = json.dumps({'event': payload.data}),
            # make message persistent
            properties = pika.BasicProperties(delivery_mode = 2))
        trace("data sent")
        connection.close()


################################################################################
class Consumer(Channel):
    
    def doWorkCallback(channel, method, properties, body):
        Consumer.Instance.doWork(channel, method, properties, body)

    Instance = None

    def __init__(self):
         Consumer.Instance = self

    def run(self):
        _, channel = self.connectRabbitmq()
        channel.basic_qos(prefetch_count = 1)
        channel.basic_consume(Consumer.doWorkCallback, queue = DEFAULT_QUEUE)
        trace("Consumer.run: waiting for messages")
        channel.start_consuming()


    def doWork(self, channel, method, properties, body):
        trace("Consumer.doWork: data received")

        data = json.loads(body.decode())
        payload = Payload(data['event'])

        myProject = Project(payload)
        myApp = GitHubApp(payload.installation)

        # first check_run to get the repo
        trace("")
        jobToRun = Job(CHECK_RUN_STEP_1_NAME, payload, myProject, myApp,
            'getRepo',
            'The respository was successfully cloned',
            'Clone from {} at {}'.format(payload.clone_url, payload.head_sha),
            'Cannot get the repository: an exception was thrown')
        jobToRun.run()

        # create another check_run to compile
        trace("")
        jobToRun = Job(CHECK_RUN_STEP_2_NAME, payload, myProject, myApp,
            'compileProject',
            'Project compiled',
            'Clone from {} at {}'.format(payload.clone_url, payload.head_sha),
            'Cannot compile the project: an exception was thrown')
        jobToRun.run()

        # create another check_run to run descartes
        trace("")
        jobToRun = Job(CHECK_RUN_STEP_3_NAME, payload, myProject, myApp,
            'runDescartes',
            'Descartes completed',
            'See details for Descartes findings',
            'Descartes failed: an exception was thrown')
        jobToRun.run()

        channel.basic_ack(delivery_tag = method.delivery_tag)


################################################################################
class Payload:

    def __init__(self, jsonPayload):
        self.data = jsonPayload


    def __getattr__(self, name):
        if name == 'pull_request':
            return(self.data['pull_request'])
        elif name == 'head_sha':
            return(self.data['pull_request']['head']['sha'])
        elif name == 'head_ref':
            return(self.data['pull_request']['head']['ref'])
        elif name == 'installation':
            return(self.data['installation']['id'])
        elif name == 'clone_url':
            return(self.data['repository']['clone_url'])
        elif name == 'repo_url':
            return(self.data['repository']['url'])
        raise AttributeError(name)
        return(None)


    def isPullRequest(self):
        return('action' in self.data and self.data['action'] == 'opened'
                and 'pull_request' in self.data)


################################################################################
class GitHubApp:

    def __init__(self, installation):
        self.privateKeyFile = 'descartes_app.pem'
        self.installation = installation


    def requestToken(self):
        token_response = requests.post(GITHUB_API + 'installations/{}/access_tokens'.format(self.installation),
        headers = {
            'Authorization': 'Bearer ' + self.getJwt(),
            'Accept': 'application/vnd.github.machine-man-preview+json'
        })
        if not success(token_response):
            raise Exception('Could not get the installation access token. Code: {}, response {}'.format(token_response.status_code, token_response.text))
        return(json.loads(token_response.text)['token'])


    def getJwt(self, app_id = APP_ID):
        pemFile = self.privateKeyFile
        if os.path.exists(os.path.join('..', pemFile)):
            pemFile = os.path.join('..', pemFile)
        with open(pemFile, 'r') as _file:
            key = RSA.importKey(_file.read())
            jwtPayload = {'iat': time.time(), 'exp': time.time() + 300, 'iss': app_id}
            return(jwt.encode(jwtPayload, key.exportKey('PEM'), algorithm = 'RS256').decode('ascii'))


################################################################################
class Project:

    def __init__(self, payload):
        self.payload = payload
        self.workingDir = os.path.join('.', 'descartesWorkingDir')
        self.annotationFileName = os.path.join(self.workingDir,
                'target', 'pit-reports', 'methods.json')


    def callMethod(self, methodName):
        method = getattr(self, methodName)
        method()


    def getRepo(self):
        trace('Project.getRepo IN')
        currentDir = os.getcwd()
        if os.path.exists(self.workingDir):
            shutil.rmtree(self.workingDir)
        command = 'git clone ' + self.payload.clone_url  + ' ' + self.workingDir
        trace("getRepo: " + command)
        gitClone = subprocess.Popen(command,
        stdin = subprocess.PIPE, stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT, shell = True)
        stdoutData, stderrData = gitClone.communicate()
        if gitClone.returncode != 0:
            raise Exception('git clone failed: ' + stdoutData.decode())

        os.chdir(self.workingDir)

        command = 'git checkout ' + self.payload.head_sha
        trace("getRepo: " + command)
        gitCheckout = subprocess.Popen(command,
            stdin = subprocess.PIPE, stdout = subprocess.PIPE,
            stderr = subprocess.STDOUT, shell = True)
        stdoutData, stderrData = gitCheckout.communicate()
        os.chdir(currentDir)
        if gitCheckout.returncode != 0:
            raise Exception('git checkout failed: ' + stdoutData)


    def compileProject(self):
        trace('Project.compileProject IN')
        currentDir = os.getcwd()
        os.chdir(self.workingDir)
        command = 'mvn install'
        trace("compileProject: " + command)
        mvnInstall = subprocess.Popen(command,
            stdin = subprocess.PIPE, stdout = subprocess.PIPE,
            stderr = subprocess.STDOUT, shell = True)
        stdoutData, stderrData = mvnInstall.communicate()
        os.chdir(currentDir)
        if mvnInstall.returncode != 0:
            raise Exception(command + ' failed: ' + stdoutData.decode())


    def runDescartes(self):
        trace('Project.runDescartes IN')
        currentDir = os.getcwd()
        os.chdir(self.workingDir)

        command = 'mvn eu.stamp-project:pitmp-maven-plugin:descartes -DoutputFormats=METHODS -DtimestampedReports=false'
        trace("runDescartes: " + command)
        mvnPmp = subprocess.Popen(command,
            stdin = subprocess.PIPE, stdout = subprocess.PIPE,
            stderr = subprocess.STDOUT, shell = True)
        stdoutData, stderrData = mvnPmp.communicate()
        os.chdir(currentDir)
        if mvnPmp.returncode != 0:
            raise Exception(command + ' failed: ' + stdoutData.decode())


################################################################################
class Job:

    def __init__(self, checkRunName, payload, theProject, gitHubApp,
            commandToRun, successMessage, successSummary, errorMessage):
        self.name = checkRunName
        self.payload = payload
        self.project = theProject
        self.gitHubApp = gitHubApp
        self.command = commandToRun
        self.successMessage = successMessage
        self.successSummary = successSummary
        self.errorMessage = errorMessage


    def run(self):
        trace('Job.run IN: ' + self.name)
        checkRun = CheckRun(self.name, self.payload, self.gitHubApp)
        checkRun.start()
        checkRun.update('in_progress')

        try:
            trace(self.command)
            self.project.callMethod(self.command)
        except Exception as exc:
            trace('Job.run: ' + self.name + ': FAILED')
            checkRun.update('completed', 'failure', self.errorMessage, str(exc))
            return
        trace('Job.run: ' + self.name + ': OK')
        checkRun.update('completed', 'success', self.successMessage,
            self.successSummary, self.project.annotationFileName)


################################################################################
class CheckRun:

    def __init__(self, name, payload, gitHubApp):
        self.name = name
        self.payload = payload
        self.gitHubApp = gitHubApp
        self.checkRunInfo = None


    def start(self):
        trace('CheckRun.start: ' + self.name)
        params = {'name': self.name, 'status': 'queued',
                'head_branch': self.payload.head_ref,
                'head_sha': self.payload.head_sha}

        token = self.gitHubApp.requestToken()
        response = requests.post(self.payload.repo_url + '/check-runs',
                data = json.dumps(params),
                headers = {
                    'Authorization': 'token ' + token,
                    'Accept': 'application/vnd.github.antiope-preview+json',
                })
        if not success(response):
            raise Exception('Could not create the check run. Code {}. Response: {}'.format(response.status_code, response.text))
        self.checkRunInfo = json.loads(response.text)


    def update(self, status, conclusion = None, message = None, summary = '',
            annotationFileName = None):
        '''
        url - Must contain the check_run id at the end
        '''
        trace('CheckRun.update: ' + self.name + ": " + status)
        token = self.gitHubApp.requestToken()
        data = {'name': self.name, 'status': status}
        annotations = []
        if conclusion:
            trace('CheckRun.update: ' + self.name + ": " + conclusion)
            data['status'] = 'completed'
            data['conclusion'] = conclusion
            data['completed_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ')
            if annotationFileName and os.path.exists(annotationFileName):
                trace('CheckRun.update: file exists: ' + annotationFileName)
                with open(annotationFileName) as _file:
                    method_data = json.load(_file)
                blobs_url = self.payload.data['repository']['blobs_url']
                blob_href = blobs_url.replace('{/sha}', '/' + self.payload.head_sha)
                trace('blobs_url: ' + blobs_url + " - haed_sha: " + self.payload.head_sha + " - blob_href: " + blob_href)
                annotations = generate_annotations(method_data['methods'], blob_href)
                if annotations:
                    message = 'Testing issues found'
                    summary = 'Descartes has found {} testing issue(s)'.format(len(annotations))
                    data['conclusion'] = 'failure'
                else:
                    message = 'No testing issues'
                    summary = 'Descartes could not find any testing issues'
                    data['conclusion'] = 'success'
        if message:
            data['output'] = {'title': message, 'summary': summary, 'annotations': annotations } 
        dump(data, 'update')
        response = requests.patch(self.checkRunInfo['url'], data = json.dumps(data),
            headers = {
                'Authorization': 'token ' + token,
                'Accept': 'application/vnd.github.antiope-preview+json',
            })
        if not success(response):
            raise Exception('Could not update the check run. Code {}. Response: {}'.format(response.status_code, response.text))
