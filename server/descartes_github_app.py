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
    response = {'name': 'pseudo-tested methods', 'status': 'in_progress', 'head_branch': pull_request['head']['ref'], 'head_sha': pull_request['head']['sha']}
    gh_response = requests.post(payload['repository']['url'] + '/check-runs', \
        data=response, headers={'Authorization': 'Bearer ' + get_jwt(str(pull_request['number'])), \
        'Accept': 'application/vnd.github.antiope-preview+json'})
    if gh_response.status_code != requests.codes.ok:
        raise Exception('Status ' + str(gh_response.status_code) + gh_response.text)
    return "Done"



def dump(data, prefix='dump'):
    unique_filename = prefix + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json'
    with open(unique_filename, 'w') as _file:
        json.dump(data, _file)
    

#def hello_world():
#    payload = request.json
#    if not 'action' in payload:
#        return ''
#    if not 'check_suite' in payload:
#        return ''
#    pull_requests = payload['check_suite']['pull_requests']
#    unique_filename = 'dump_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json'
#    with open(unique_filename, 'w') as _file:
#        json.dump(request.json, _file)
#    if not pull_requests:
#        print('exiting because of no pull_requests')
#        return ''
#    pr = pull_requests[0]
#
#    response = {'name': 'finding-pseudo-tested-methods', 
#                'head_branch': pr['base']['ref'], 
#                'head_sha':pr['base']['sha'], 
#                'status': 'in_progress'}
#    print('post check-run to: ' + payload['repository']['url'] + '/check-runs')
#    print('    data: ' + response)
#    gh_response = requests.post(payload['repository']['url'] + '/check-runs', \
#        data=response, headers={'Authorization': 'Bearer ' + get_jwt(str(pr['number'])), \
#        'Accept': 'application/vnd.github.antiope-preview+json'})
#    if gh_response.status_code != requests.codes.ok:
#        raise Exception('Status ' + str(gh_response.status_code) + gh_response.text)
#    unique_filename = 'response_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.txt'
#    with open(unique_filename, 'w') as _file:
#        json.dump(gh_response.text, _file)
#
#    unique_filename = 'payload_' + str(uuid.uuid4()) + '.json'
#    with open(unique_filename, 'w') as _file:
#        json.dump(request.json, _file)
#    return "Done"

################################################################################
# functions
def get_jwt(issue):
    with open('descartes_app.pem', 'r') as _file:
        key = RSA.importKey(_file.read())
        jwtPayload = {'iat': time.time(), 'exp': time.time() + 600, 'iss': issue}
        return jwt.encode(jwtPayload, key.exportKey('PEM'), algorithm='RS256').decode('utf8')
