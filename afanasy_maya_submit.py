#!/usr/bin/env python
# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractmethod
from shiboken2 import wrapInstance
import maya.OpenMayaUI as OpenMayaUI
import maya.cmds as cmds
import pymel.core as pm
import afcommon
import af
import os
import sys
import shlex

CGRU_HOME = "D:/cgru.3.2.0"
CGRU_LIBS = "{}/lib/python".format(CGRU_HOME)
CGRU_AFANASY = "{}/afanasy/python".format(CGRU_HOME)
CGRU_PLUGINS = "{}/plugins/maya".format(CGRU_HOME)

MODES = ['One job (one block - all layers)',
         'One job (one block - one layer)',
         'Multiply jobs (one job - one layer)']

for path in [CGRU_LIBS, CGRU_AFANASY]:
    if path not in sys.path:
        sys.path.append(path)

os.environ['CGRU_LOCATION'] = CGRU_HOME


try:

    from PySide2.QtGui import *
    from PySide2.QtWidgets import *
    from PySide2.QtCore import *

except ImportError:

    from PySide.QtGui import *
    from PySide.QtCore import *


class Submit(metaclass=ABCMeta):

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

    @abstractmethod
    def build_command(self):
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def generate_preview(self):
        pass


class MayaSubmit(Submit):

    def build_command(self,
                      scene_full_path='',
                      render_layer=None,
                      camera=None,
                      project=None,
                      by_frame=1):

        command = ['mayarender']

        command.append('-r file')
        command.append('-s @#@ -e @#@ -b {}'.format(by_frame))

        if camera:
            command.append('-cam "{}"'.format(camera))

        if render_layer:
            command.append('-rl "{}"'.format(render_layer))

        if project:
            command.append('-proj "{}"'.format(os.path.normpath(project)))

        if scene_full_path:
            command.append(scene_full_path)

        return ' '.join(command)

    def start(self,
              render_directory='',
              scene_full_path='',
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
        jobs, blocks = [], []

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
                layer_outputs = render_directory

                if layer_name != 'defaultRenderLayer':
                    replace_name = layer_name.replace('rs_', '')
                    layer_outputs = render_directory.replace(
                        'masterLayer', replace_name)

                if generate_previews:
                    outputs_split = self.generate_preview(block, layer_outputs)
                    block.setFiles(outputs_split)

                block.setNumeric(start_frame, end_frame,
                                 frames_per_task, by_frame)
                block.setErrorsAvoidHost(self.errors_avoid_host)
                block.setErrorsRetries(self.errors_retries)
                block.setErrorsTaskSameHost(self.errors_task_same_host)
                block.setErrorsForgiveTime(self.errors_forgive_time)

                command = self.build_command(scene_full_path=scene_full_path,
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
                outputs_split = self.generate_preview(block, render_directory)
                block.setFiles(outputs_split)

            command = self.build_command(scene_full_path=scene_full_path,
                                         camera=camera,
                                         project=project,
                                         by_frame=by_frame)

            block.setNumeric(start_frame, end_frame, frames_per_task, by_frame)
            block.setCommand(command)
            blocks.append(block)

        result = []

        for job in jobs:

            job.setAnnotation(annotation)
            job.setDependMaskGlobal(self.depend_mask_global)
            job.setHostsMask(self.hosts_mask)
            job.setHostsMaskExclude(self.hosts_exclude)
            job.setTimeLife(self.life_time *
                            3600 if self.life_time > 0 else 240 * 3600)

            if mode in [0, 1]:
                job.blocks.extend(blocks)

            status, data = job.send()
            result.append((status, data))

        return result

    def generate_preview(self, block, outputs):
        block.setFiles(
            afcommon.patternFromDigits(
                afcommon.patternFromStdC(
                    afcommon.patternFromPaths(outputs, '')
                )
            ).split(';')
        )


def log_decorator(func):

    def run(*args, **kwargs):

        redshift = pm.PyNode('redshiftOptions')
        stored_log_level = redshift.logLevel.get()
        redshift.logLevel.set(2)

        func(*args, **kwargs)

        redshift.logLevel.set(stored_log_level)

    return run


class StatusDialog(QDialog):

    def __init__(self, message='', parent=None):
        super(StatusDialog, self).__init__(parent)

        q_btn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        self.buttonBox = QDialogButtonBox(q_btn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        self.result = QTextEdit()

        self.result.insertPlainText(message)

        self.layout.addWidget(QLabel("Info:"))
        self.layout.addWidget(self.result)
        self.layout.addWidget(self.buttonBox)

        self.setLayout(self.layout)
        self.setWindowTitle("Submit job info")
        self.setMinimumSize(400, 100)


class MayaSubmitUI(QMainWindow):

    def __init__(self,
                 file_name_prefix='',
                 mode=1,
                 frame_per_task=1,
                 start_frame=1,
                 end_frame=1,
                 by_frame=1,
                 parent=None):

        if parent is None:
            parent = self._maya_main_window()

        QCoreApplication.setOrganizationName("ToyRoy")
        QCoreApplication.setOrganizationDomain("")
        QCoreApplication.setApplicationName("MayaSubmit")

        super(MayaSubmitUI, self).__init__(parent)

        self.settings = QSettings()
        self.parent = parent

        self.file_name_prefix = file_name_prefix
        self.mode = mode
        self.frame_per_task = frame_per_task
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.by_frame = by_frame

        self._init_widgets()
        self._init_connections()
        self._init_settings()

    def _init_widgets(self):

        self.centralWidget = QWidget(self)
        main_layout = QVBoxLayout(self.centralWidget)
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)

        self.file_name_prefix_widget = QLineEdit('')
        self.start_frame_widget = QLineEdit()
        self.end_frame_widget = QLineEdit()
        self.frame_per_task_widget = QLineEdit('1')
        self.by_frame_widget = QLineEdit('1')
        self.mode_widget = QComboBox()

        self.mode_widget.addItems(MODES)

        for line_edit in [self.start_frame_widget, self.end_frame_widget,
                          self.frame_per_task_widget, self.by_frame_widget]:
            line_edit.setValidator(QIntValidator())

        grid_layout.addWidget(QLabel("File name prefix"), 0, 0)
        grid_layout.addWidget(self.file_name_prefix_widget, 0, 1)

        grid_layout.addWidget(QLabel("Mode"), 1, 0)
        grid_layout.addWidget(self.mode_widget, 1, 1)

        grid_layout.addWidget(QLabel("Frame per task"), 2, 0)
        grid_layout.addWidget(self.frame_per_task_widget, 2, 1)

        grid_layout.addWidget(QLabel("Start frame"), 3, 0)
        grid_layout.addWidget(self.start_frame_widget, 3, 1)

        grid_layout.addWidget(QLabel("End frame"), 4, 0)
        grid_layout.addWidget(self.end_frame_widget, 4, 1)

        grid_layout.addWidget(QLabel("By frame"), 5, 0)
        grid_layout.addWidget(self.by_frame_widget, 5, 1)

        self.submit_button = QPushButton("Submit job")

        main_layout.addWidget(grid_widget)
        main_layout.addWidget(self.submit_button)
        main_layout.setAlignment(Qt.AlignTop)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setCentralWidget(self.centralWidget)

    def _init_connections(self):
        self.submit_button.clicked.connect(self.maya_submit_job)

    def _init_settings(self):

        self.setGeometry(0, 0, 700, 50)
        self.setWindowTitle('Afanasy Maya Submiter')
        self._set_to_center()
        self.restoreState(self.settings.value('state'))
        self.restoreGeometry(self.settings.value('geometry'))

        prev_settings = self.settings.value('prev_settings')

        if prev_settings:
            self.by_frame = prev_settings.get('by_frame') or '1'
            self.frame_per_task = prev_settings.get('frame_per_task') or '1'
            self.mode = prev_settings.get('mode') or 0

        self.file_name_prefix_widget.setText(self.file_name_prefix)
        self.start_frame_widget.setText(str(self.start_frame))
        self.end_frame_widget.setText(str(self.end_frame))
        self.by_frame_widget.setText(str(self.by_frame))
        self.frame_per_task_widget.setText(str(self.frame_per_task))
        self.mode_widget.setCurrentIndex(self.mode)

    @log_decorator
    def maya_submit_job(self):

        render_directory = self.file_name_prefix_widget.text()
        render_globals = pm.PyNode('defaultRenderGlobals')
        prev_value = render_globals.imageFilePrefix.get()

        render_globals.imageFilePrefix.set(render_directory)

        cmds.file(save=True, type="mayaAscii")

        scene_full_path = pm.sceneName()
        job_name = os.path.basename(scene_full_path)
        start_frame = int(float(self.start_frame_widget.text()))
        end_frame = int(float(self.end_frame_widget.text()))
        by_frame = int(float(self.by_frame_widget.text()))
        frame_per_task = int(float(self.frame_per_task_widget.text()))
        mode = self.mode_widget.currentIndex()

        submitter = MayaSubmit()
        result = submitter.start(render_directory=render_directory,
                                 scene_full_path=scene_full_path,
                                 mode=mode,
                                 job_name=job_name,
                                 start_frame=start_frame,
                                 end_frame=end_frame,
                                 frames_per_task=frame_per_task,
                                 by_frame=by_frame,
                                 annotation='',
                                 generate_previews=False,)

        if result:

            job_status = []

            for status, data in result:

                if not status:
                    message = "Job submit with error"
                    break
                else:
                    job_status.append(data['id'])

            else:
                message = ['Job succesfull started with id {}\n'.format(
                    job_id) for job_id in job_status]
                message = ''.join(message)

            status_dialog = StatusDialog(message=message)
            status_dialog.exec_()

        render_globals.imageFilePrefix.set(prev_value)

    def closeEvent(self, _):
        self.settings.setValue('state', self.saveState())
        self.settings.setValue('geometry', self.saveGeometry())

        settings_kwargs = {
            'by_frame': self.by_frame_widget.text(),
            'frame_per_task': self.frame_per_task_widget.text(),
            'mode': self.mode_widget.currentIndex(),
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

    render_globals = pm.PyNode('defaultRenderGlobals')
    file_name_prefix = render_globals.imageFilePrefix.get()

    start_frame = cmds.playbackOptions(query=True, minTime=True)
    end_frame = cmds.playbackOptions(query=True, maxTime=True)

    submit_window = MayaSubmitUI(file_name_prefix=file_name_prefix,
                                 start_frame=start_frame,
                                 end_frame=end_frame)
    submit_window.show()
