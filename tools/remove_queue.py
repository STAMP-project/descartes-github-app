#!/usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################

import pika

DEFAULT_QUEUE = 'descartes'
#DEFAULT_QUEUE = 'simple_tests'
#DEFAULT_QUEUE = 'executions'

################################################################################
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.queue_delete(DEFAULT_QUEUE)
connection.close()
