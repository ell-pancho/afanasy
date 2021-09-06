#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Пример импорта библиотеки af

import os
import sys
import platform

try:
    import af

except ImportError:

    cgru_dirs = {
        'Windows': 'c:/tools/cgru.2.3.0', 
        'Linux': '/opt/cgru'
        }

    os.environ['CGRU_LOCATION'] = cgru_dirs[platform.system()]

    sys.path.append('%s/afanasy/python' % os.environ['CGRU_LOCATION'])
    sys.path.append('%s/lib/python' % os.environ['CGRU_LOCATION'])

    import af

AF_HOST_MASK = 'lnx.*'
AF_HOST_EXCLUDE_MASK = ''
AF_BLOCK_SERVICE = 'maya'
PRVZ_APP = 'mayapy'
AF_JOB_LIFETIME = 432000  # Время жизни задачи в секундах. 0 - Бесконечно.
AF_JOB_PAUSED = False

# Пример отправки задачи на ферму

command = 'maya -batch -file {}/scene.mb -command "afanasyBatch(@#@,@#@,1,1)"'.format(os.getcwd())

job = af.Job('Maya Example')

block = af.Block('render', 'maya')
block.setCommand(command)
block.setNumeric(1, 5, 2)

job.blocks.append(block)
job.send()

# Также для каждого блока можно добавлять таски

job_name = 'test_job'
job = af.Job(job_name)
job.setTimeLife(AF_JOB_LIFETIME)

block = af.Block('block_name', 'maya')
block.setHostsMask('lnx.*') # этот таск будет рендерится только на машинах с такой маской

task = af.Task('task_name')
task.setCommand(command)

block.tasks.append(task)

job.blocks.append(block)
result = job.send()
