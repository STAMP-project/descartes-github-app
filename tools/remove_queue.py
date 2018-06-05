#!/usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################

import pika
import argparse

################################################################################
myParser = argparse.ArgumentParser()
myParser.add_argument('queue_name', nargs='1', \
   help = 'Name of the rabbitMQ queue to remove; you can use: "sudo rabbitmqctl list_queues" to see the queues.')
myArgs = myParser.parse_args()

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.queue_delete(myArgs.queue_name)
connection.close()
