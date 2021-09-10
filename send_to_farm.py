# -*- coding: utf-8 -*-
import os
import sys

path1 = r'D:\cgru.3.2.0\lib\python'
path2 = r'D:\cgru.3.2.0\afanasy\python'

for path in [path1, path2]:
    if path not in sys.path:
        sys.path.append(path)

os.environ['CGRU_LOCATION'] = 'D:/cgru.3.2.0'

import af


def send_job():

    start_frame = 1
    end_frame = 1
    frames_per_task = 1
    by_frame = 1
    depend_mask_global = ''
    hosts_mask = 'ws102'
    hosts_exclude = ''
    life_time = 1
    annotation = 'Annotation'

    frames_per_task = max(1, frames_per_task)
    by_frame = max(1, by_frame)

    scene_name = "D:/test_scene/maya_redshift_render_test.ma"
    filename = 'maya_redshift_render_test.ma'
    outputs = "C:/Users/mskadmin/Documents/maya/projects/default/images"

    job_name = os.path.basename(scene_name)
    
    command = 'mayarender '
    command += '-s @#@ -e @#@ -b %d ' % by_frame
    command += scene_name

    job = af.Job(job_name)

    block = af.Block('MayaTestRedshift', 'maya_redshift')
    block.setNumeric(start_frame, end_frame, frames_per_task, by_frame)
    block.setCommand(command)

    job.setAnnotation(annotation)
    job.setFolder('input', os.path.dirname(scene_name))
    job.setFolder('output', outputs)
    job.setDependMaskGlobal(depend_mask_global)
    job.setHostsMask(hosts_mask)
    job.setHostsMaskExclude(hosts_exclude)

    if life_time > 0:
        job.setTimeLife(life_time * 3600)
    else:
        job.setTimeLife(240 * 3600)

    job.blocks.append(block)

    status, data = job.send()

send_job()
