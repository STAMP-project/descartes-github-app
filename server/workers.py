import os
import json
import pika
import time
import subprocess

from descartes_github_app import update_check_run, dump

DEFAULT_QUEUE = 'executions'

def connect():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(DEFAULT_QUEUE, durable=True)
    return connection, channel

def create_work(data):
    connection, channel = connect()    
    channel.basic_publish(
        exchange='', 
        routing_key=DEFAULT_QUEUE, 
        body=json.dumps(data),
        properties=pika.BasicProperties(delivery_mode=2) # make message persistent
    ) 
    connection.close()


def run_consumer():
    _, channel = connect()
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(do_work, queue=DEFAULT_QUEUE)
    channel.start_consuming()


def do_work(ch, method, properties, body):
    data = json.loads(body)

    update_url = data['check_run']['url']
    installation = data['event']['installation']['id']
    update_check_run(update_url, 'in_progress', installation)

    url = data['event']['repository']['clone_url']
    sha = data['event']['pull_request']['head']['sha']

    try:
        get_repo(update_url, sha)
    except Exception as exc:
        update_check_run(update_url, 'completed', installation, conclusion='failure', output={
            'title': 'An exception was thrown',
            'summary': str(exc)
        })
        return
    update_check_run(update_url, 'completed', installation, conclusion='success', output={
            'title': 'The respository was successfully cloned',
            'summary': 'Clone from {} at {}'.format(update_url, sha)
        })
    ch.basic_ack(delivery_tag = method.delivery_tag)

def get_repo(cloneUrl, commitSha):
    workingDir = 'descartesWorkingDir'
    command = 'git clone ' + cloneUrl  + ' ' + workingDir
    gitClone = subprocess.Popen(command,
        stdin = subprocess.PIPE, stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT, shell = True)
    stdoutData, stderrData = gitClone.communicate()
    if gitClone.returncode != 0:
        raise Exception('git clone failed: ' + stdoutData)

    os.chdir(workingDir)

    command = 'git checkout ' + commitSha
    gitCheckout = subprocess.Popen(command,
        stdin = subprocess.PIPE, stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT, shell = True)
    stdoutData, stderrData = gitCheckout.communicate()
    if gitCheckout.returncode != 0:
        raise Exception('git checkout failed: ' + stdoutData)


if __name__ == '__main__':
    run_consumer()
