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

## Yet Another shallow comment

GITHUB_API = 'https://api.github.com/'
APP_ID = 12748
CHECK_RUN_STEP_1_NAME = 'Getting repository'
CHECK_RUN_STEP_2_NAME = 'Looking for pseudo-tested methods'

DEFAULT_QUEUE = 'descartes'

################################################################################
# don't change the variable name 'application' otherwise uwsgi won't work anymore
application = Flask(__name__)

################################################################################
# requests
@application.route('/', methods=['GET', 'POST'])
def pullrequest_opened():
    payload = request.json
    dump(payload, 'other')
    if not 'action' in payload or payload['action'] != 'opened' or not 'pull_request' in payload:
        return 'No pull request event', 400
    dump(payload, 'pr')
    pull_request = payload['pull_request']

    # move the start_check_run into consumer, i.e. ?
    #information = start_check_run(
    #    payload['installation']['id'], 
    #    payload['repository']['url'], 
    #    {
    #        'name': CHECK_RUN_STEP_1_NAME,
    #        'status': 'queued',
    #        'head_branch': pull_request['head']['ref'],
    #        'head_sha': pull_request['head']['sha']
    #    })

    #dump(information, 'information')
    #create_work({'event': payload, 'check_run': information})
    create_work({'event': payload})
    return 'Everything went well :)'


def dump(data, prefix='dump'):
    unique_filename = prefix + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json'
    with open(unique_filename, 'w') as _file:
        json.dump(data, _file)


def start_check_run(installation, repo_url, params):
    token = request_token(installation)
    response = requests.post(repo_url + '/check-runs', 
            data= json.dumps(params),
            headers={
                'Authorization': 'token ' + token,  
                'Accept': 'application/vnd.github.antiope-preview+json',
            })
    trace("start_check_run")
    if not success(response):
        raise Exception('Could not create the check run. Code {}. Response: {}'.format(response.status_code, response.text))
    return json.loads(response.text)


def update_check_run(url, status, installation, checkRunName, conclusion=None, output=None):
    '''
    url - Must contain the check_run id at the end
    '''
    token = request_token(installation)
    data = {'name': checkRunName, 'status': status}
    if conclusion:
        data['status'] = 'completed'
        data['conclusion'] = conclusion
        data['completed_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ')
    if output:
        data['output'] = output
    response = requests.patch(url, data=json.dumps(data), headers = {
        'Authorization': 'token ' + token,  
        'Accept': 'application/vnd.github.antiope-preview+json',
    })
    trace("update_check_run: " + checkRunName)
    if not success(response):
        raise Exception('Could not update the check run. Code {}. Response: {}'.format(response.status_code, response.text))


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

def get_jwt(app_id=APP_ID):
    with open('descartes_app.pem', 'r') as _file:
        key = RSA.importKey(_file.read())
        jwtPayload = {'iat': time.time(), 'exp': time.time() + 300, 'iss': app_id}
        return jwt.encode(jwtPayload, key.exportKey('PEM'), algorithm='RS256').decode('ascii')

def connect_rabbitmq():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(DEFAULT_QUEUE, durable=True)
    return connection, channel

def create_work(data):
    connection, channel = connect_rabbitmq()    
    channel.basic_publish(
        exchange='', 
        routing_key=DEFAULT_QUEUE, 
        body=json.dumps(data),
        properties=pika.BasicProperties(delivery_mode=2) # make message persistent
    ) 
    trace("data sent")
    connection.close()


def run_consumer():
    _, channel = connect_rabbitmq()
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(do_work, queue=DEFAULT_QUEUE)
    trace("waiting for messages")
    channel.start_consuming()


def do_work(channel, method, properties, body):
    trace("data received")

    data = json.loads(body.decode())

    installation = data['event']['installation']['id']
    pull_request = data['event']['pull_request']

    # first check run: getting repo
    information = start_check_run(
        installation, 
        data['event']['repository']['url'], 
        {
            'name': CHECK_RUN_STEP_1_NAME,
            'status': 'queued',
            'head_branch': pull_request['head']['ref'],
            'head_sha': pull_request['head']['sha']
        })

    update_url = information['url']
    update_check_run(update_url, 'in_progress', installation, CHECK_RUN_STEP_1_NAME)

    url = data['event']['repository']['clone_url']
    sha = data['event']['pull_request']['head']['sha']

    try:
        get_repo(url, sha)
    except Exception as exc:
        update_check_run(update_url, 'completed', installation, CHECK_RUN_STEP_1_NAME,
            conclusion='failure',
            output={
                'title': 'Cannot get the repositroy: an exception was thrown',
                'summary': str(exc)
        })
        return
    trace("do_work: update_check_run " + CHECK_RUN_STEP_1_NAME)
    update_check_run(update_url, 'completed', installation, CHECK_RUN_STEP_1_NAME,
        conclusion='success',
        output={
            'title': 'The respository was successfully cloned',
            'summary': 'Clone from {} at {}'.format(update_url, sha)
        })
    # create another check_run to run descartes
    #trace("do_work: start_check_run " + CHECK_RUN_STEP_2_NAME)
    #information = start_check_run(
    #    installation,
    #    data['event']['repository']['url'],
    #    {
    #        'name': CHECK_RUN_STEP_2_NAME,
    #        'status': 'in_progress',
    #        'head_branch': data['event']['pull_request']['head']['ref'],
    #        'head_sha': data['event']['pull_request']['head']['sha']
    #    })
    #try:
    #    run_descartes()
    #except Exception as exc:
    #    update_check_run(update_url, 'completed', installation, CHECK_RUN_STEP_2_NAME,
    #        conclusion='failure',
    #        output={
    #            'title': 'Descartes failed: an exception was thrown',
    #            'summary': str(exc)
    #    })
    #    return
    ## complete the result with annotations
    #trace("do_work: update_check_run " + CHECK_RUN_STEP_2_NAME)
    #update_check_run(update_url, 'completed', installation, CHECK_RUN_STEP_2_NAME,
    #    conclusion='success',
    #    output={
    #        'title': 'Descartes completed',
    #        'summary': 'The mutation score is: '
    #    })
    channel.basic_ack(delivery_tag = method.delivery_tag)


def get_repo(cloneUrl, commitSha):
    currentDir = os.getcwd()
    workingDir = './descartesWorkingDir'
    if os.path.exists(workingDir):
        shutil.rmtree(workingDir)
    command = 'git clone ' + cloneUrl  + ' ' + workingDir
    trace("get_repo: " + command)
    gitClone = subprocess.Popen(command,
        stdin = subprocess.PIPE, stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT, shell = True)
    stdoutData, stderrData = gitClone.communicate()
    if gitClone.returncode != 0:
        raise Exception('git clone failed: ' + stdoutData.decode())

    os.chdir(workingDir)

    command = 'git checkout ' + commitSha
    trace("get_repo: " + command)
    gitCheckout = subprocess.Popen(command,
        stdin = subprocess.PIPE, stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT, shell = True)
    stdoutData, stderrData = gitCheckout.communicate()
    os.chdir(currentDir)
    if gitCheckout.returncode != 0:
        raise Exception('git checkout failed: ' + stdoutData)


def run_descartes(cloneUrl, commitSha):
    currentDir = os.getcwd()
    workingDir = './descartesWorkingDir'
    os.chdir(workingDir)
    command = 'mvn install'
    trace("run_descartes: " + command)
    mvnInstall = subprocess.Popen(command,
        stdin = subprocess.PIPE, stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT, shell = True)
    stdoutData, stderrData = gitClone.communicate()
    if gitClone.returncode != 0:
        raise Exception(command + ' failed: ' + stdoutData.decode())

    command = 'mvn eu.stamp-project:pitmp-maven-plugin:descartes'
    trace("run_descartes: " + command)
    mvnInstall = subprocess.Popen(command,
        stdin = subprocess.PIPE, stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT, shell = True)
    stdoutData, stderrData = gitClone.communicate()
    if gitClone.returncode != 0:
        raise Exception(command + ' failed: ' + stdoutData.decode())


def trace(message):
    print("######## " + message, file=sys.stderr)
