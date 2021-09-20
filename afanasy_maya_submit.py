#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

CGRU_HOME = "D:/cgru.3.2.1"
CGRU_LIBS = "{}/lib/python".format(CGRU_HOME)
CGRU_AFANASY = "{}/afanasy/python".format(CGRU_HOME)
CGRU_PLUGINS = "{}/plugins/maya".format(CGRU_HOME)

MODES = ['One job (single block with all layers)', 
         'One job (with multiply blocks)', 
         'Multiply jobs (single block per layer)']

for path in [CGRU_LIBS, CGRU_AFANASY]:
    if path not in sys.path:
        sys.path.append(path)
        
os.environ['CGRU_LOCATION'] = CGRU_HOME

import af
import afcommon
import pymel.core as pm
import maya.cmds as cmds
import maya.OpenMayaUI as OpenMayaUI
from shiboken2 import wrapInstance

try:

    from PySide2.QtGui import *
    from PySide2.QtWidgets import *
    from PySide2.QtCore import *

except ImportError:

    from PySide.QtGui import *
    from PySide.QtCore import *


class Submit:
    
    def __init__(self, 
                 depend_mask_global='',
                 hosts_mask='ws102',
                 hosts_exclude='',
                 errors_avoid_host=1,
                 errors_retries=1,
                 errors_task_same_host=1,
                 errors_forgive_time=18000,
                 life_time=1):
        
        self.depend_mask_global = depend_mask_global
        self.hosts_mask = hosts_mask
        self.hosts_exclude = hosts_exclude
        self.errors_avoid_host = errors_avoid_host
        self.errors_retries = errors_retries
        self.errors_task_same_host = errors_task_same_host
        self.errors_forgive_time = errors_forgive_time
        self.life_time = life_time
    
    def build_command(self):
        pass
    
    def start(self):
        pass
    
    def generate_preview(self):
        pass
    

class MayaSubmit(Submit):
    
    def build_command(self,
                      file_full_path='', 
                      render_layer=None,
                      camera=None,
                      project=None,
                      by_frame=1):
        
        command = ['mayarender']
        
        command.append('-s @#@ -e @#@ -b {}'.format(by_frame))
        
        if camera:
            command.append(' -cam {}'.format(camera))

        if render_layer:
            command.append('-rl {}'.format(render_layer))

        if project:
            command.append('-proj {}'.format(os.path.normpath(project)))

        command.append(file_full_path)

        return ' '.join(command)

    def start(self, 
              inputs='',
              outputs='',
              file_full_path='',
              camera=None,
              project=None,
              mode=1,
              job_name='afanasy_maya_submit',
              start_frame=1,
              end_frame=1,
              frames_per_task=1,
              by_frame=1,
              annotation='',
              generate_previews=False,
              ):
        
        if start_frame > end_frame:
            temp = end_frame
            end_frame = start_frame
            start_frame = temp
        
        frames_per_task = max(1, frames_per_task)
        by_frame = max(1, by_frame)
        
        jobs = []
        blocks = []
        
        if mode in [0, 1]:
            job = af.Job(job_name)
            jobs.append(job)

        if mode in [1, 2]:
            
            rlm = pm.PyNode('renderLayerManager')
            layers = [layer for layer in rlm.connections(type=pm.nt.RenderLayer)
                      if layer.renderable.get()]

            for layer in layers:
                
                layer_name = layer.name()
                block = af.Block(layer_name, 'maya_redshift')
                layer_outputs = outputs
                
                if layer_name != 'defaultRenderLayer':
    
                    replace_name = layer_name.replace('rs_', '')
                    layer_outputs = outputs.replace('masterLayer', replace_name)

                if generate_previews:
                    outputs_split = self.generate_preview(block, layer_outputs)
                    block.setFiles(outputs_split)

                block.setNumeric(start_frame, end_frame, frames_per_task, by_frame)
                block.setErrorsAvoidHost(self.errors_avoid_host)
                block.setErrorsRetries(self.errors_retries)
                block.setErrorsTaskSameHost(self.errors_task_same_host)
                block.setErrorsForgiveTime(self.errors_forgive_time)
                
                command = self.build_command(file_full_path=file_full_path,
                                             render_layer=layer_name,
                                             camera=camera,
                                             project=project,
                                             by_frame=by_frame)

                block.setCommand(command)

                if mode == 1:
                    blocks.append(block)
                else:
                    job = af.Job('%s - %s' % (job_name, layer_name))

                    job.blocks = [block]
                    jobs.append(job)

        else:
            
            block = af.Block('All Layers', 'maya_redshift')

            if generate_previews:
                outputs_split = self.generate_preview(block, outputs)
                block.setFiles(outputs_split)
                
            command = self.build_command(file_full_path=file_full_path,
                                         camera=camera,
                                         project=project,
                                         by_frame=by_frame)

            block.setNumeric(start_frame, end_frame, frames_per_task, by_frame)
            block.setCommand(command)
            blocks.append(block)

        for job in jobs:
            
            job.setAnnotation(annotation)
            
            job.setFolder('input', inputs)
            job.setFolder('output', os.path.dirname(outputs))
            
            job.setDependMaskGlobal(self.depend_mask_global)
            job.setHostsMask(self.hosts_mask)
            job.setHostsMaskExclude(self.hosts_exclude)

            job.setTimeLife(self.life_time * 3600 if self.life_time > 0 else 240 * 3600)

            if mode in [0, 1]:
                job.blocks.extend(blocks)

            status, _ = job.send()
            
            if not status:
                pm.PopupError('Something went wrong!')
                
    def generate_preview(self, block, outputs):
        block.setFiles(
            afcommon.patternFromDigits(
                afcommon.patternFromStdC(
                    afcommon.patternFromPaths(outputs)
                )
            ).split(';')
        )
                

def log_decorator(func):
    
    def run(*args, **kwargs):
        
        redshift = pm.PyNode('redshiftOptions')
        stored_log_level = redshift.logLevel.get()
        redshift.logLevel.set(2)
        
        cmds.file(save=True, type="mayaAscii")
        
        func(*args, **kwargs)
        
        redshift.logLevel.set(stored_log_level)
        
    return run


class MayaSubmitUI(QMainWindow):
    
    def __init__(self, parent=None):

        if parent is None:
            parent = self._maya_main_window()
            
        QCoreApplication.setOrganizationName("ToyRoy")
        QCoreApplication.setOrganizationDomain("")
        QCoreApplication.setApplicationName("MayaSubmit")
        
        super(MayaSubmitUI, self).__init__(parent)

        self.settings = QSettings()
        self.parent = parent

        self._init_widgets()
        self._init_connections()
        self._init_settings()

    def _init_widgets(self):
        
        self.centralWidget = QWidget(self)
        main_layout = QVBoxLayout(self.centralWidget)
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)

        self.file_name_prefix = QLineEdit('')
        self.start_frame = QLineEdit()
        self.end_frame = QLineEdit()
        self.frame_per_task = QLineEdit('1')
        self.by_frame = QLineEdit('1')
        self.mode = QComboBox()
        
        self.mode.addItems(MODES)
        
        for line_edit in [self.start_frame, self.end_frame, 
                          self.frame_per_task, self.by_frame]:
            line_edit.setValidator(QIntValidator())
            
        grid_layout.addWidget(QLabel("File name prefix"), 0, 0)
        grid_layout.addWidget(self.file_name_prefix, 0, 1)
        
        grid_layout.addWidget(QLabel("Mode"), 1, 0)
        grid_layout.addWidget(self.mode, 1, 1)
        
        grid_layout.addWidget(QLabel("Frame per task"), 2, 0)
        grid_layout.addWidget(self.frame_per_task, 2, 1)

        grid_layout.addWidget(QLabel("Start frame"), 3, 0)
        grid_layout.addWidget(self.start_frame, 3, 1)

        grid_layout.addWidget(QLabel("End frame"), 4, 0)
        grid_layout.addWidget(self.end_frame, 4, 1)

        grid_layout.addWidget(QLabel("By frame"), 5, 0)
        grid_layout.addWidget(self.by_frame, 5, 1)
        
        self.submit_button = QPushButton("Submit job")

        main_layout.addWidget(grid_widget)
        main_layout.addWidget(self.submit_button)
        main_layout.setAlignment(Qt.AlignTop)
        
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setCentralWidget(self.centralWidget)

    def _init_connections(self):
        self.submit_button.clicked.connect(self.maya_submit_job)
    
    def _init_settings(self):
        
        outputs = pm.renderSettings(fullPath=1, 
                                    firstImageName=1, 
                                    lastImageName=1,
                                    leaveUnmatchedTokens=1, 
                                    customTokenString="RenderPass=Beauty")[0]
        
        self.file_name_prefix.setText(outputs)
        self.start_frame.setText(str(cmds.playbackOptions(query=True, minTime=True)))
        self.end_frame.setText(str(cmds.playbackOptions(query=True, maxTime=True)))

        self.setGeometry(0, 0, 700, 50)
        self.setWindowTitle('Afanasy Maya Submiter')
        self._set_to_center()
        
        self.restoreState(self.settings.value('state'))
        self.restoreGeometry(self.settings.value('geometry'))

        prev_settings = self.settings.value('prev_settings')

        if prev_settings:
            by_frame = prev_settings.get('by_frame') or '1'
            frame_per_task = prev_settings.get('frame_per_task') or '1'
            mode = prev_settings.get('mode') or 0

            self.by_frame.setText(by_frame)
            self.frame_per_task.setText(frame_per_task)
            self.mode.setCurrentIndex(mode)
    
    @log_decorator
    def maya_submit_job(self):
        file_full_path = pm.sceneName()
        job_name = os.path.basename(file_full_path)
        project_path = 'D:/output'
        start_frame = int(float(self.start_frame.text()))
        end_frame = int(float(self.end_frame.text()))
        by_frame = int(float(self.by_frame.text()))
        frame_per_task = int(self.frame_per_task.text())
        output = self.file_name_prefix.text()
        mode = self.mode.currentIndex()
        
        submitter = MayaSubmit()
        submitter.start(inputs='',
                        outputs=output,
                        file_full_path=file_full_path,
                        camera=None,
                        project=project_path,
                        mode=mode,
                        job_name=job_name,
                        start_frame=start_frame,
                        end_frame=end_frame,
                        frames_per_task=frame_per_task,
                        by_frame=by_frame,
                        annotation='',
                        generate_previews=False,)
        
    def closeEvent(self, _):
        self.settings.setValue('state', self.saveState())
        self.settings.setValue('geometry', self.saveGeometry())

        settings_kwargs = {
            'by_frame': self.by_frame.text(),
            'frame_per_task': self.frame_per_task.text(),
            'mode': self.mode.currentIndex(),
        }

        self.settings.setValue('prev_settings', settings_kwargs)
    
    def _set_to_center(self):
        q_rect = self.frameGeometry()
        center = QDesktopWidget().availableGeometry().center()

        q_rect.moveCenter(center)
        self.move(q_rect.topLeft())

    @staticmethod
    def _maya_main_window():
        main_window_ptr = OpenMayaUI.MQtUtil.mainWindow()
        return wrapInstance(int(main_window_ptr), QWidget)


if __name__ == '__main__':
    submit_window = MayaSubmitUI()
    submit_window.show()