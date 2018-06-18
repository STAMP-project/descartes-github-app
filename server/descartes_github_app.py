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
    dump(payload, 'other')
    if not payload.isPullRequest():
        return 'No pull request event', 400
    dump(payload, 'pr')

    # this send the message to the consumer
    # the consumer can be either run manually (workers.py) to debug
    # or run as a service to deploy
    sender = Producer()
    sender.createWork(payload)

    return 'Everything went well :)'


################################################################################
# functions
def dump(data, prefix = 'dump'):
    unique_filename = prefix + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json'
    with open(unique_filename, 'w') as _file:
        json.dump(data, _file)


def trace(message):
    print("######## " + message, file = sys.stderr)


################################################################################
class Payload:

    def __init(self, jsonPayload):
        data = jsonPayload


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
        result = False
        if 'action' in data and data['action'] == 'opened' and 'pull_request' in payload:
           result = True
        return(result)


################################################################################
class PullRequest:

    def __init(self, jsonPullRequest):
        data = jsonPullRequest


################################################################################
class CheckRun:

    def __init(self, name, payload):
        self.name = name
        self.payload = payload
        self.checkRunInfo = None

    def start(self):
        params = {'name': self.name, 'status': 'queued',
                'head_branch': self.payload.head_ref,
                'head_sha': self.payload.head_sha}

        token = request_token(self.payload.installation)
        response = requests.post(self.payload.repo_url + '/check-runs', 
                data = json.dumps(params),
                headers = {
                    'Authorization': 'token ' + token,  
                    'Accept': 'application/vnd.github.antiope-preview+json',
                })
        trace("start_check_run")
        if not success(response):
            raise Exception('Could not create the check run. Code {}. Response: {}'.format(response.status_code, response.text))
        self.checkRunInfo = json.loads(response.text)
    
    
    def update(self, status, conclusion = None, message = None, summary = ''):
        '''
        url - Must contain the check_run id at the end
        '''
        token = request_token(self.payload.installation)
        data = {'name': checkRunName, 'status': status}
        if conclusion:
            data['status'] = 'completed'
            data['conclusion'] = conclusion
            data['completed_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ')
        if message:
            data['output'] = {'title': message, 'summary': summary }
        response = requests.patch(self.checkRunInfo['url'], data = json.dumps(data),
            headers = {
                'Authorization': 'token ' + token,  
                'Accept': 'application/vnd.github.antiope-preview+json',
            })
        trace("CheckRun.update: " + checkRunName)
        if not success(response):
            raise Exception('Could not update the check run. Code {}. Response: {}'.format(response.status_code, response.text))



################################################################################
class GitHubToken:

    def __init__(self):

    def request_token(installation):
        token_response = requests.post(GITHUB_API + 'installations/{}/access_tokens'.format(installation),
        headers = {
            'Authorization': 'Bearer ' + get_jwt(),
            'Accept': 'application/vnd.github.machine-man-preview+json'  
        })
        if not success(token_response):
            raise Exception('Could not get the installation access token. Code: {}, response {}'.format(token_response.status_code, token_response.text))
        return json.loads(token_response.text)['token']
    
    
    def success(response):
        return 200 <= response.status_code < 300
    
    
    def get_jwt(app_id = APP_ID):
        pemFile = 'descartes_app.pem'
        if os.path.exists(os.path.join('..', pemFile)):
            pemFile = os.path.join('..', pemFile)
        with open(pemFile, 'r') as _file:
            key = RSA.importKey(_file.read())
            jwtPayload = {'iat': time.time(), 'exp': time.time() + 300, 'iss': app_id}
            return jwt.encode(jwtPayload, key.exportKey('PEM'), algorithm = 'RS256').decode('ascii')

################################################################################
class Producer:

    def createWork(self, payload):
        connection, channel = connectRabbitmq()    
        channel.basic_publish(exchange = '', routing_key = DEFAULT_QUEUE, 
            body = json.dumps({'event': payload.data}),
            # make message persistent
            properties = pika.BasicProperties(delivery_mode = 2)) 
        trace("data sent")
        connection.close()


    def connectRabbitmq(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters \
            (host = 'localhost'))
        channel = connection.channel()
        channel.queue_declare(DEFAULT_QUEUE, durable = True)
        return connection, channel


################################################################################
# RabbitMQ callback
def doWorkCallback(channel, method, properties, body):
    Consumer.Instance.doWork(channel, method, properties, body)

class Consumer:

    Instance = None

    def __init__(self):
         Consumer.Instance = self

    def run(self):
        _, channel = connect_rabbitmq()
        channel.basic_qos(prefetch_count = 1)
        channel.basic_consume(doWorkCallback, queue = DEFAULT_QUEUE)
        trace("waiting for messages")
        channel.start_consuming()
    
    
    def doWork(self, channel, method, properties, body):
        trace("data received")
    
        data = json.loads(body.decode())
        payload = Payload(data['event'])
    
        myProject = Project(payload)

        # first check_run to get the repo
        jobToRun = Job(CHECK_RUN_STEP_1_NAME, payload, myProject, 'getRepo()',
            'The respository was successfully cloned',
            'Clone from {} at {}'.format(clone_url, sha),
            'Cannot get the repositroy: an exception was thrown')
        jobToRun.run(globals(), locals())
    
        # create another check_run to compile
        jobToRun = Job(CHECK_RUN_STEP_2_NAME, payload, myProject, 'compileProject()',
            'Project compiled',
            'Clone from {} at {}'.format(clone_url, sha),
            'Cannot compile the project: an exception was thrown')
        jobToRun.run(globals(), locals())
    
        # create another check_run to run descartes
        jobToRun = Job(CHECK_RUN_STEP_3_NAME, payload, myProject, 'runDescartes()',
            'Descartes completed',,
            'See details for Descartes findings',
            'Descartes failed: an exception was thrown')
        jobToRun.run(globals(), locals())
    
        channel.basic_ack(delivery_tag = method.delivery_tag)


################################################################################
class Job:

    def __init__(self, checkRunName, payload, theProject, commandToRun, successMessage,
            successSummary, errorMessage):
        self.name = checkRunName
        self.payload = payload
        self.project = theProject
        self.command = commandToRun
        self.successMessage = successMessage
        self.successSummary = successSummary
        self.errorMessage = errorMessage


    def run(self, globalDict, localDict):
        checkRun = CheckRun(self.name, self.payload)
        checkRun.start()
        checkRun.update('in_progress')
    
        try:
            eval('self.project.' + self.command, globalDict, localDict)
        except Exception as exc:
            checkRun.update('completed', 'failure', self.errorMessage, str(exc))
            return
        checkRun.update('completed', 'success', self.successMessage,
            self.successSummary)


################################################################################
class Project:

    def __init__(self, payload):
        self.payload = payload
        self.workingDir = './descartesWorkingDir'

    def getRepo(self):
        currentDir = os.getcwd()
        if os.path.exists(self.workingDir):
            shutil.rmtree(self.workingDir)
        command = 'git clone ' + self.payload.clone_url  + ' ' + workingDir
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
        currentDir = os.getcwd()
        os.chdir(self.workingDir)
    
        command = 'mvn eu.stamp-project:pitmp-maven-plugin:descartes'
        trace("runDescartes: " + command)
        mvnPmp = subprocess.Popen(command,
            stdin = subprocess.PIPE, stdout = subprocess.PIPE,
            stderr = subprocess.STDOUT, shell = True)
        stdoutData, stderrData = mvnPmp.communicate()
        os.chdir(currentDir)
        if mvnPmp.returncode != 0:
            raise Exception(command + ' failed: ' + stdoutData.decode())
