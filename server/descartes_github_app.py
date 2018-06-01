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

## Shallow comment

GITHUB_API = 'https://api.github.com/'
APP_ID = 12748
CHECK_RUN_NAME = 'Looking for pseudo-tested methods'
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

    information = start_check_run(
        payload['installation']['id'], 
        payload['repository']['url'], 
        {
            'name': CHECK_RUN_NAME,
            'status': 'in_progress',
            'head_branch': pull_request['head']['ref'],
            'head_sha': pull_request['head']['sha']
        })

    dump(information, 'information')
    return 'Everything went well :)'

def dump(data, prefix='dump'):
    unique_filename = prefix + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json'
    with open(unique_filename, 'w') as _file:
        json.dump(data, _file)

def start_check_run(installation, url, params):
    token = request_token(installation)
    response = requests.post(url, 
            data= json.dumps(params),
            headers={
                'Authorization': 'token ' + token,  
                'Accept': 'application/vnd.github.antiope-preview+json',
            })
    if response.status_code != 200:
        raise Exception('Could not create the check run. Code {}. Response: {}'.format(response.status_code, response.text))
    return json.loads(response.text)

def request_token(installation):
    token_response = requests.post(GITHUB_API + 'installation/{}/access_tokens'.format(installation),
    headers = {
        'Authorization': 'Bearer ' + get_jwt(),
        'Accept': 'application/vnd.github.machine-man-preview+json'  
    })
    if token_response.status_code != 200:
        raise Exception('Could not get the installation access token. Code: {}, response {}'.format(token_response.status_code, token_response.text))
    return token_response['token']

def get_jwt(app_id=APP_ID):
    with open('private2.pem', 'r') as _file:
        key = RSA.importKey(_file.read())
        jwtPayload = {'iat': time.time(), 'exp': time.time() + 300, 'iss': app_id}
        return jwt.encode(jwtPayload, key.exportKey('PEM'), algorithm='RS256').decode('ascii')
