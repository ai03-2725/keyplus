#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2017 jem@seethis.link
# Licensed under the MIT license (http://opensource.org/licenses/MIT)

from __future__ import absolute_import, division, print_function, unicode_literals

from PySide.QtGui import (
    QMainWindow, QTextEdit, QAction, QApplication, QPushButton, QProgressBar,
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QLineEdit, QGroupBox,
    QFormLayout, QScrollArea, QSizePolicy, QGridLayout, QComboBox,
    QStackedLayout, QMessageBox, QFileDialog, QErrorMessage, QTableView,
    QFont, QDialog, QTabWidget
)
from PySide.QtGui import QIcon, QIntValidator
from PySide.QtCore import Qt, QBasicTimer, QSize , QFileInfo, QTimer
from PySide.QtCore import Slot, Signal, QAbstractTableModel

# TODO: clean up directory structure
import sys
import datetime, time, binascii
import yaml

import easyhid
import protocol
import layout.parser
import xusb_boot

STATUS_BAR_TIMEOUT=4500

if 1:
    # debug settings
    DEFAULT_LAYOUT_FILE = "../layouts/basic_split_test.yaml"
    DEFAULT_RF_FILE = "../layouts/test_rf_config.yaml"
    DEFAULT_FIRMWARE_FILE = ""
    DEFAULT_DEVICE_ID = 10
else:
    DEFAULT_LAYOUT_FILE = ""
    DEFAULT_RF_FILE = ""
    DEFAULT_FIRMWARE_FILE = ""
    DEFAULT_DEVICE_ID = ''

def error_msg_box(msg, title="Error"):
    errorBox = QMessageBox()
    errorBox.setWindowTitle(title)
    errorBox.setText(msg)
    errorBox.exec_()

def msg_box(description="", title="Message"):
    msgBox = QMessageBox()
    msgBox.setWindowTitle(title)
    msgBox.setText(description)
    msgBox.exec_()

def is_keyplus_device(device):
    if device.interface_number != protocol.DEFAULT_INTERFACE:
        return False
    return (device.vendor_id, device.product_id) in [(0x6666, 0x1111*i) for i in range(16)]

def is_xusb_bootloader_device(device):
    # if device.interface_number != xusb_boot.DEFAULT_INTERFACE:
    #     return False
    return (device.vendor_id, device.product_id) == (xusb_boot.DEFAULT_VID, xusb_boot.DEFAULT_PID)

def is_nrf24lu1p_bootloader_device(device):
    ID_VENDOR = 0x1915
    ID_PRODUCT = 0x0101
    return (device.vendor_id, device.product_id) == (ID_VENDOR, ID_PRODUCT)

def is_unifying_bootloader_device(device):
    return False

def is_supported_device(device):
    return is_keyplus_device(device) or is_xusb_bootloader_device(device) or \
        is_nrf24lu1p_bootloader_device(device) or is_unifying_bootloader_device(device)

def is_bootloader_device(device):
    return is_xusb_bootloader_device(device) or \
        is_nrf24lu1p_bootloader_device(device) or \
        is_unifying_bootloader_device(device)

class DeviceWidget(QGroupBox):

    PROGRAM_SIGNAL = 0
    INFO_SIGNAL = 1

    program = Signal(str)
    show_info = Signal(str)
    reset = Signal(str)

    def __init__(self, device):
        super(DeviceWidget, self).__init__(None)

        self.device = device
        self.label = None

        self.initUI()

    # label for generic keyplus device
    def setup_keyplus_label(self):
        try:
            self.device.open()
            settingsInfo = protocol.get_device_info(self.device)
            firmwareInfo = protocol.get_firmware_info(self.device)
            self.device.close()
        except TimeoutError as err:
            # Incase opening the device fails
            raise Exception ("Error Opening Device: {} | {}:{}"
                    .format(
                        self.device.path,
                        self.device.vendor_id,
                        self.device.product_id
                    ),
                  file=sys.stderr
            )

        if settingsInfo.crc == settingsInfo.computed_crc:
            build_time_str = protocol.timestamp_to_str(settingsInfo.timestamp)
            self.label = QLabel('{} | {} | Firmware v{}.{}.{}\n'
                                'Device id: {}\n'
                                'Serial number: {}\n'
                                'Last time updated: {}'
                .format(
                    self.device.manufacturer_string,
                    self.device.product_string,
                    firmwareInfo.version_major,
                    firmwareInfo.version_minor,
                    firmwareInfo.version_patch,
                    settingsInfo.id,
                    self.device.serial_number,
                    build_time_str
                )
            )
        else:
            # CRC doesn't match
            if settingsInfo.is_empty:
                self.label = QLabel('??? | ??? | Firmware v{}.{}.{}\n'
                                    'Warning: Empty settings!\n'
                                    'Serial number: {}\n'
                    .format(
                        firmwareInfo.version_major,
                        firmwareInfo.version_minor,
                        firmwareInfo.version_patch,
                        self.device.serial_number,
                    )
                )
            else:
                # corrupt settings in the flash
                build_time_str = protocol.timestamp_to_str(settingsInfo.timestamp)
                self.label = QLabel('??? | ??? | Firmware v{}.{}.{}\n'
                                    'WARNING: Settings are uninitialized\n'
                                    'Serial number: {}\n'
                    .format(
                        firmwareInfo.version_major,
                        firmwareInfo.version_minor,
                        firmwareInfo.version_patch,
                        self.device.serial_number,
                    )
                )

    # xusb_boot bootloader device
    def setup_xusb_bootloader_label(self):
        try:
            self.device.open()
            bootloader_info = xusb_boot.get_boot_info(self.device)
            self.device.close()
        except TimeoutError as err:
            # Incase opening the device fails
            raise Exception ("Error Opening Device: {} | {}:{}"
                    .format(
                        self.device.path,
                        self.device.vendor_id,
                        self.device.product_id
                    ),
                  file=sys.stderr
            )

        self.label = QLabel('{} | {} | Bootloader v{}.{}\n'
                            'MCU: {}\n'
                            'Flash size: {}\n'
                            'Serial number: {}\n'
            .format(
                self.device.manufacturer_string,
                self.device.product_string,
                bootloader_info.version_major,
                bootloader_info.version_minor,
                bootloader_info.mcu_string,
                bootloader_info.flash_size,
                self.device.serial_number
            )
        )

    # nrf24lu1p
    def setup_nrf24lu1p_label(self):
        # try:
        #     self.device.open()
        #     bootloader_info = xusb_boot.get_boot_info(self.device)
        #     self.device.close()
        # except TimeoutError as err:
        #     # Incase opening the device fails
        #     raise Exception ("Error Opening Device: {} | {}:{}"
        #             .format(
        #                 self.device.path,
        #                 self.device.vendor_id,
        #                 self.device.product_id
        #             ),
        #           file=sys.stderr
        #     )

        self.label = QLabel('nRF24LU1+ Bootloader v{}.{}\n'
                            'MCU: nRF24LU1+\n'
            .format(
                0,
                0,
                self.device.manufacturer_string,
                self.device.product_string,
            )
        )

    def initUI(self):
        programIcon = QIcon('img/download.png')
        infoIcon = QIcon('img/info.png')

        if is_keyplus_device(self.device):
            self.setup_keyplus_label()
        elif is_xusb_bootloader_device(self.device):
            self.setup_xusb_bootloader_label()
        elif is_nrf24lu1p_bootloader_device(self.device):
            self.setup_nrf24lu1p_label()
        else:
            raise Exception("Unsupported USB device {}:{}".format(
                self.device.vendor_id, self.device.product_id))

        if self.label == None:
            return

        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.label.setStyleSheet("""
        QLabel {
            background: #FFF;
            border: 1px solid;
            padding: 2px;
            font: 11pt;
        }
        """)
        self.label.setFixedHeight(90)
        self.label.setMinimumWidth(390)

        self.programButton = QPushButton(' Program')
        self.programButton.setIcon(programIcon)
        self.programButton.clicked.connect(self.programSignal)

        if is_bootloader_device(self.device):
            self.secondaryButton = QPushButton('Reset')
            self.secondaryButton.clicked.connect(self.resetSignal)
        else:
            self.secondaryButton = QPushButton('Info')
            self.secondaryButton.setIcon(infoIcon)
            self.secondaryButton.clicked.connect(self.infoSignal)

        self.layout = QGridLayout()
        self.layout.addWidget(self.label, 0, 0, 2, 1)
        self.layout.addWidget(self.programButton, 0, 1)
        self.layout.addWidget(self.secondaryButton, 1, 1)
        self.setLayout(self.layout)

        self.setMaximumHeight(150)
        self.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #CCC;
            }
        """)

    def infoSignal(self):
        self.show_info.emit(self.device.path)

    def resetSignal(self):
        self.reset.emit(self.device.path)

    def programSignal(self):
        self.program.emit(self.device.path)

    def sizeHint(self):
        return QSize(560, 0)

class DeviceInformationWindow(QDialog):
    def __init__(self, parent, header, device_settings, firmware_settings,
                 error_codes, *args):
        QDialog.__init__(self, parent, *args)
        self.setGeometry(300, 200, 570, 450)
        self.setWindowTitle("Device information")
        table_model = DeviceInformationTable(self, header, device_settings)
        dev_settings_table = QTableView()
        dev_settings_table.setModel(table_model)

        table_model = DeviceInformationTable(self, header, firmware_settings)
        fw_settings_table = QTableView()
        fw_settings_table.setModel(table_model)

        table_model = DeviceInformationTable(self, header, error_codes)
        error_code_table = QTableView()
        error_code_table.setModel(table_model)

        # set font
        # font = QFont("monospace", 10)
        font = QFont("", 10)
        dev_settings_table.setFont(font)
        fw_settings_table.setFont(font)
        # set column width to fit contents (set font first!)
        dev_settings_table.resizeColumnsToContents()
        fw_settings_table.resizeColumnsToContents()
        error_code_table.resizeColumnsToContents()

        tab_view = QTabWidget()
        tab_view.addTab(dev_settings_table, "User settings")
        tab_view.addTab(fw_settings_table, "Firmware settings")
        tab_view.addTab(error_code_table, "Error Codes")

        layout = QVBoxLayout(self)
        layout.addWidget(tab_view)
        self.setLayout(layout)

class DeviceInformationTable(QAbstractTableModel):
    def __init__(self, parent, header, data_list, *args):
        QAbstractTableModel.__init__(self, parent, *args)
        self.data_list = data_list
        self.header = header

    def rowCount(self, parent):
        return len(self.data_list)

    def columnCount(self, parent):
        if len(self.data_list) == 0:
            return 0
        else:
            return len(self.data_list[0])

    def data(self, index, role):
        if not index.isValid():
            return None
        elif role != Qt.DisplayRole:
            return None
        return self.data_list[index.row()][index.column()]

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header[col]
        return None

class DeviceList(QScrollArea):
    def __init__(self, programming_handler, info_handler, reset_handler):
        super(DeviceList, self).__init__()

        self.deviceWidgets = []
        self.programming_handler = programming_handler
        self.info_handler = info_handler
        self.reset_handler = reset_handler
        self.updateCounter = 0

        self.initUI()

    def initUI(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.listWidget = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.listWidget.setLayout(self.layout)
        self.setWidgetResizable(True)

        self.setWidget(self.listWidget)

        self.updateList()

    def updateList(self):
        self.updateCounter += 1

        deviceInfoList = list(filter(is_supported_device, easyhid.Enumeration().find()))

        deleteList = []
        deviceIds = [dev.path for dev in deviceInfoList]
        oldDevices = []
        newDevices = []

        # look at the list of connected devices and find out which devices are
        # no longer connected and remove them
        i = 0
        while i < self.layout.count():
            devItem = self.layout.itemAt(i).widget()
            if hasattr(devItem, "device") and (devItem.device.path in deviceIds):
                oldDevices.append(devItem.device)
                i += 1
            else:
                self.layout.takeAt(i).widget().deleteLater()

        # Now find the list of new devices
        oldDeviceIds = [dev.path for dev in oldDevices]
        for dev in deviceInfoList:
            if dev.path in oldDeviceIds:
                continue
            else:
                newDevices.append(dev)

        for devInfo in newDevices:
            devWidget = DeviceWidget(devInfo)
            if devWidget.label:
                self.deviceWidgets.append(devWidget)
                self.layout.addWidget(devWidget)
                devWidget.program.connect(self.programming_handler)
                devWidget.show_info.connect(self.info_handler)
                devWidget.reset.connect(self.reset_handler)

        # if len(self.deviceWidgets) == 0:
        if len(oldDevices) == 0 and len(newDevices) == 0:
            n = self.updateCounter % 4
            label = QLabel("Scanning for devices" + "." * n + " " * (4-n))
            self.layout.setAlignment(Qt.AlignCenter)
            self.layout.addWidget(label)
            self.deviceWidgets = []
        else:
            self.layout.setAlignment(Qt.AlignTop)
            self.updateCounter = 0

class FileSelector(QWidget):
    ScopeLayout = 0
    ScopeDevice = 1
    ScopeFirmware = 2
    ScopeAll = 3

    def __init__(self):
        super(FileSelector, self).__init__()

        self.initUI()
        self.lastDir = None

    def initUI(self):

        self.scopeSelector = QComboBox()
        self.scopeSelector.addItem("Layout", FileSelector.ScopeLayout)
        self.scopeSelector.addItem("Device and RF", FileSelector.ScopeDevice)
        self.scopeSelector.addItem("Firmware Update", FileSelector.ScopeFirmware)
        # self.scopeSelector.addItem("All", FileSelector.ScopeAll)

        self.scopeSelector.currentIndexChanged.connect(self.scopeUpdate)

        self.layoutSettings = LayoutSettingsScope()
        self.deviceSettings = DeviceSettingsScope()
        self.firmwareSettings = FirmwareSettingsScope()

        self.scope = None

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.scopeSelector)

        self.stackedLayout = QStackedLayout()
        self.stackedLayout.addWidget(self.layoutSettings)
        self.stackedLayout.addWidget(self.deviceSettings)
        self.stackedLayout.addWidget(self.firmwareSettings)

        self.layout.addLayout(self.stackedLayout)

        self.setMinimumSize(0, 300)

        self.setLayout(self.layout)
        # self.updateUI(FileSelector.ScopeLayout)

    def scopeUpdate(self, index):
        self.stackedLayout.setCurrentIndex(index)

    def updateUI(self, scope):
        if self.scope == scope:
            return

        self.layout.removeWidget(self.layoutSettings)
        self.layout.removeWidget(self.deviceSettings)
        self.layout.removeWidget(self.firmwareSettings)

        if scope == FileSelector.ScopeLayout:
            self.layout.addWidget(self.layoutSettings)
        elif scope == FileSelector.ScopeDevice:
            self.layout.addWidget(self.deviceSettings)
        elif scope == FileSelector.ScopeFirmware:
            self.layout.addWidget(self.firmwareSettings)
        elif scope == FileSelector.ScopeAll:
            self.layout.addWidget(self.layoutSettings)
            self.layout.addWidget(self.deviceSettings)
            self.layout.addWidget(self.firmwareSettings)

    def getProgramingInfo(self):
        return self.scopeSelector.currentIndex()

    def getFirmwareFile(self):
        return self.firmwareSettings.getFirmwareFile()

    def getLayoutFile(self):
        return self.layoutSettings.getLayoutFile()

    def getRFLayoutFile(self):
        return self.deviceSettings.getCurrentSettings()[2]

    def getRFFile(self):
        return self.deviceSettings.getCurrentSettings()[1]

    def getTargetID(self):
        return self.deviceSettings.getCurrentSettings()[0]

class LayoutSettingsScope(QGroupBox):

    def __init__(self, parent=None):
        super(LayoutSettingsScope, self).__init__("Layout settings:")

        self.initUI()

    def initUI(self):
        self.fileWidget = FileBrowseWidget("Layout file (*.yaml)")
        self.fileWidget.setText(DEFAULT_LAYOUT_FILE)
        layout = QFormLayout()
        layout.addRow(QLabel("Layout file (.yaml): "), self.fileWidget)
        label = QLabel("<b>Note:</b> Each device that can act as a "
                       "wireless/wired receiver stores its own copy of the "
                       "layout settings. The other devices will still function "
                       "when the layout is updated, but they will use their "
                       "old version of the layout instead. "
                       "You can intentionally load different layouts on different "
                       "keyboard components to have different layout options depending "
                       "on which device is acting as the receiver."
                       )
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setWordWrap(True)
        layout.addRow(label)
        self.setLayout(layout)

    def getLayoutFile(self):
        return self.fileWidget.text()

class DeviceSettingsScope(QGroupBox):
    def __init__(self):
        super(DeviceSettingsScope, self).__init__("Device and RF settings:")

        self.initUI()

    def initUI(self):
        self.layoutFile = FileBrowseWidget("Layout settings file .yaml (*.yaml)")
        self.layoutFile.setText(DEFAULT_LAYOUT_FILE)
        self.rfSettingsFile = FileBrowseWidget("Device settings file .yaml (*.yaml)")
        self.rfSettingsFile.setText(DEFAULT_RF_FILE)
        layout = QFormLayout()
        layout.addRow(QLabel("Layout settings file (.yaml):"), self.layoutFile)
        layout.addRow(QLabel("RF settings file (.yaml):"), self.rfSettingsFile)
        self.idLine = QLineEdit()
        self.idLine.setText(str(DEFAULT_DEVICE_ID))
        self.idLine.setMaximumWidth(50)
        self.idLine.setValidator(QIntValidator(0, 63))
        layout.addRow(QLabel("Device id (0-63):"), self.idLine)

        self.generateButton = QPushButton("Generate new RF settings")
        self.generateButton.setMaximumWidth(230)
        self.generateButton.clicked.connect(self.generateRFSettings)
        layout.addRow(None, self.generateButton)

        label = QLabel("<b>Note:</b> These settings only need to be loaded on each "
                       "device once and are persistent when you update the layout. "
                       "To ensure proper operation and security, each device must "
                       "have a unique device ID for a given RF settings file. "
                       "Since RF settings file contains your encryption key, make "
                       "sure to keep it secret.")
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setWordWrap(True)
        layout.addRow(label)
        self.setLayout(layout)

    def generateRFSettings(self):
        result = QFileDialog.getSaveFileName(
            self, "Save file", FileBrowseWidget.lastDirectory, "RF settings .yaml (*.yaml)")
        fname = result[0]
        if fname != '':
            fileInfo = QFileInfo(fname)
            try:
                FileBrowseWidget.lastDir = fileInfo.baseName()
            except:
                pass

            try:
                rf_settings = layout.parser.RFSettings.from_rand()
                timeNow = datetime.datetime.now().strftime("%Y-%M-%d at %H:%M")
                with open(fname, 'w') as outFile:
                    outFile.write(
                        "# Generated on {}\n".format(timeNow) +
                        rf_settings.to_yaml()
                    )
                self.rfSettingsFile.lineEdit.setText(fname)
            except IOError as e:
                # TODO: proper error message
                print("error writing file: " + str(e))

    def getCurrentSettings(self):
        rawID = self.idLine.text()
        if rawID == '':
            rawID = None
        else:
            rawID = int(rawID)
        return (
            rawID,
            self.rfSettingsFile.lineEdit.text(),
            self.layoutFile.lineEdit.text()
        )


class FirmwareSettingsScope(QGroupBox):
    def __init__(self):
        super(FirmwareSettingsScope, self).__init__("Firmware Update:")

        self.initUI()

    def initUI(self):
        self.fileWidget = FileBrowseWidget("Firmware file .hex (*.hex)")
        self.fileWidget.setText(DEFAULT_FIRMWARE_FILE)
        layout = QFormLayout()
        layout.addRow(QLabel("Firmware file (.hex):"), self.fileWidget)
        label = QLabel("<b>Note:</b> after updating the firmware, all layout "
                       "and device settings will be erased.")
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addRow(label)
        self.setLayout(layout)

    def getFirmwareFile(self):
        return self.fileWidget.text()


class FileBrowseWidget(QWidget):
    lastDirectory = None

    def __init__(self, fileType="Layout File (*.yaml)"):
        super(FileBrowseWidget, self).__init__()

        self.fileTypeName = fileType

        self.initUI()

    def initUI(self):
        # hbox = QHBoxLayout()
        hbox = QGridLayout()

        self.lineEdit = QLineEdit()
        self.browseButton = QPushButton("Browse")

        hbox.addWidget(self.lineEdit, 0, 0, )
        hbox.addWidget(self.browseButton, 0, 1)
        hbox.setContentsMargins(0, 0, 0, 0)

        self.browseButton.clicked.connect(self.grabFileName)

        self.setLayout(hbox)

    def setText(self, val):
        self.lineEdit.setText(val)

    def text(self):
        return self.lineEdit.text()

    def grabFileName(self):
        result = QFileDialog.getOpenFileName(
            self, "Open file", FileBrowseWidget.lastDirectory, self.fileTypeName)
        fname = result[0]
        if fname != '':
            fileInfo = QFileInfo(fname)
            try:
                FileBrowseWidget.lastDir = fileInfo.baseName()
            except:
                pass
            self.lineEdit.setText(fname)


class Loader(QMainWindow):
    def __init__(self, parent=None):
        super(Loader, self).__init__(parent)

        self.initUI()

    def updateDeviceList(self):
        self.statusBar().showMessage("Device list updating...", timeout=STATUS_BAR_TIMEOUT)
        self.deviceListWidget.updateList()
        self.statusBar().showMessage("Device list updated finished!", timeout=STATUS_BAR_TIMEOUT)

    def getFileName(self, ext):
        fname = QFileDialog.getOpenFileName(self, 'Open file', '/home')
        # if fname[0]:
        #     f = open(fname[0], 'r')

        #     with f:
        #         data = f.read()
        #         self.textEdit.setText(data)

    def initUI(self):

        # textEdit = QTextEdit()
        # self.setCentralWidget(textEdit)

        # self.setStyleSheet("QGroupBox {  border: 1px solid gray; padding: 5px;}");

        # Action to quit program
        exitAction = QAction(QIcon(None), 'Quit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(self.close)

        # # Action to update device list
        # self.refreshAction = QAction(QIcon('img/reload.png'), 'Refresh', self)
        # self.refreshAction.setShortcut('F5')
        # self.refreshAction.setStatusTip('Refresh list of connected devices.')
        # self.refreshAction.triggered.connect(self.updateDeviceList)

        # Action to show program information
        helpAction = QAction(QIcon(None), 'Help', self)
        helpAction.setShortcut('F1')
        helpAction.triggered.connect(self.showHelpDialog)

        # Action to help
        aboutAction = QAction(QIcon(None), 'About', self)
        aboutAction.triggered.connect(self.showAboutDialog)

        self.statusBar()

        # Add the file menu
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        # fileMenu.addAction(self.refreshAction)
        fileMenu.addAction(exitAction)
        fileMenu = menubar.addMenu('&Help')
        fileMenu.addAction(helpAction)
        fileMenu.addAction(aboutAction)

        # # Add the toolbar
        # toolbar = self.addToolBar('Exit')
        # # toolbar.addAction(self.refreshAction)
        # toolbar.setMovable(False)

        # Add the main windows widgets
        self.deviceListWidget = DeviceList(
            self.programDeviceHandler,
            self.infoDeviceHandler,
            self.resetDeviceHandler
        )
        self.fileSelectorWidget = FileSelector()

        self.setStyleSheet("""
            QStatusBar {
                border-top: 1px solid #CCC;
            }
            QToolBar {
                border-top: 1px solid #DDD;
                border-bottom: 1px solid #CCC;
            }
        """)

        gbox = QGroupBox("Connected USB devices:")
        gboxLayout = QVBoxLayout()
        gboxLayout.addWidget(self.deviceListWidget)
        gbox.setLayout(gboxLayout)

        self.refreshEvent = QTimer()
        self.refreshEvent.setInterval(1250)
        self.refreshEvent.timeout.connect(self.USBUpdate)
        self.refreshEvent.start()

        layout = QVBoxLayout()
        layout.addWidget(self.fileSelectorWidget)
        layout.addWidget(gbox)
        self.setCentralWidget(QWidget())
        self.centralWidget().setLayout(layout)

        self.setMinimumSize(620, 700)
        self.setMaximumWidth(620)
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)

        self.setGeometry(300, 300, 350, 250)
        self.setWindowTitle('keyplus layout and firmware loader')
        self.show()

    def process_layout(self, layout_json_obj, layout_file, device_id):
        try:
            settings_gen = layout.parser.SettingsGenerator(layout_json_obj, None)
            layout_data = settings_gen.gen_layout_section(device_id)
            settings_data = settings_gen.gen_settings_section(device_id)
            return layout_data, settings_data
        except (layout.parser.ParseError, layout.parser.ParseKeycodeError) as err:
            error_msg_box(str(err))
            self.statusBar().showMessage(
                'Error parsing "{}"'.format(layout_file),
                timeout=STATUS_BAR_TIMEOUT*2
            )
            return None, None

    def abort_update(self, target_device):
        try:
            target_device.close()
        except:
            pass

        self.deviceListWidget.updateList()

    @Slot(str)
    def programDeviceHandler(self, device_path):
        target_device = self.tryOpenDevicePath(device_path)

        if target_device == None:
            self.abort_update(target_device)
            return

        programmingMode = self.fileSelectorWidget.getProgramingInfo()

        if is_bootloader_device(target_device) and programmingMode != FileSelector.ScopeFirmware:
            error_msg_box("Can only upload firmware while bootloader is running. "
                          "Either reset it, or upload a firmware hex instead")
            self.abort_update(target_device)
            return

        if programmingMode == FileSelector.ScopeLayout:
            self.statusBar().showMessage("Started updating layout", timeout=STATUS_BAR_TIMEOUT)

            layout_file = self.fileSelectorWidget.getLayoutFile()

            if layout_file == '':
                error_msg_box("No layout file given.")
                self.abort_update(target_device)
                return
            else:
                pass

            layout_json_obj = None
            with open(layout_file) as file_obj:
                try:
                    layout_json_obj = yaml.safe_load(file_obj.read())
                except Exception as err:
                    error_msg_box("Syntax error in yaml file: " + str(err))
                    self.abort_update(target_device)
                    return

            device_info = protocol.get_device_info(target_device)
            layout_data, settings_data = self.process_layout(layout_json_obj, layout_file, device_info.id)
            if layout_data == None or settings_data == None:
                return

            protocol.update_layout_section(target_device, layout_data)
            protocol.update_settings_section(target_device, settings_data, keep_rf=True)
            protocol.reset_device(target_device)

            self.statusBar().showMessage("Finished updating layout", timeout=STATUS_BAR_TIMEOUT)
        elif programmingMode == FileSelector.ScopeDevice:
            layout_file = self.fileSelectorWidget.getRFLayoutFile()
            rf_file = self.fileSelectorWidget.getRFFile()
            target_id = self.fileSelectorWidget.getTargetID()

            self.statusBar().showMessage("Started updating RF settings", timeout=STATUS_BAR_TIMEOUT)

            if layout_file == '':
                error_msg_box("No layout file given.")
                self.abort_update(target_device)
                return
            elif rf_file == '':
                error_msg_box("No RF settings file given.")
                self.abort_update(target_device)
                return
            elif target_id == None:
                error_msg_box("No device id file given.")
                self.abort_update(target_device)
                return

            layout_json_obj = None
            rf_json_obj = None
            with open(layout_file) as file_obj:
                try:
                    layout_json_obj = yaml.safe_load(file_obj.read())
                except Exception as err:
                    error_msg_box("Syntax error in yaml file: " + str(err))
                    self.abort_update(target_device)
                    return
            with open(rf_file) as file_obj:
                try:
                    rf_json_obj = yaml.safe_load(file_obj.read())
                except Exception as err:
                    error_msg_box("Syntax error in yaml file: " + str(err))
                    self.abort_update(target_device)
                    return

            try:
                settings_gen = layout.parser.SettingsGenerator(layout_json_obj, rf_json_obj)
            except ParseError as err:
                error_msg_box("Error Generating RF settings data: " + str(err))
                self.abort_update(target_device)
                return

            layout_data = settings_gen.gen_layout_section(target_id)
            settings_data = settings_gen.gen_settings_section(target_id)

            protocol.update_settings_section(target_device, settings_data)
            protocol.update_layout_section(target_device, layout_data)
            protocol.reset_device(target_device)

            self.statusBar().showMessage("Finished updating RF settings", timeout=STATUS_BAR_TIMEOUT)

        elif programmingMode == FileSelector.ScopeFirmware:
            fw_file = self.fileSelectorWidget.getFirmwareFile()

            self.statusBar().showMessage("Starting update firmware", timeout=STATUS_BAR_TIMEOUT)

            if fw_file == '':
                error_msg_box("No firmware file given.")
            else:

                if is_xusb_bootloader_device(target_device):
                    self.program_xusb_boot_firmware_hex(target_device, fw_file)
                elif is_keyplus_device(target_device):
                    try:
                        serial_num = target_device.serial_number
                        boot_vid, boot_pid = protocol.enter_bootloader(target_device)

                        self.bootloaderProgramTimer = QTimer()
                        self.bootloaderProgramTimer.setInterval(3000)
                        self.bootloaderProgramTimer.setSingleShot(True)
                        self.bootloaderProgramTimer.timeout.connect( lambda:
                            self.programFirmwareHex(boot_vid, boot_pid, serial_num, fw_file)
                        )
                        self.bootloaderProgramTimer.start()
                    except (easyhid.HIDException, protocol.KBProtocolException):
                        error_msg_box("Programming hex file failed: '{}'".format(fw_file))
        else:
            try:
                target_device.close()
            except:
                pass
            raise Exception("Unimplementend programming mode")


    def programFirmwareHex(self, boot_vid, boot_pid, serial_num, file_name):
        device = None

        for i in range(1):
            en = easyhid.Enumeration(vid=boot_vid, pid=boot_pid).find()

            # Look for devices with matching serial_num number
            for dev in en:
                if dev.serial_number == serial_num:
                    device = dev
                    break

            # if a device was found with matching vid:pid, but it doesn't have
            # a matching serial_num number, then assume that the bootloader/firmware
            # doesn't set the serial_num number to the same value, so just program
            # the first matching device
            if len(en) != 0:
                device = en[0]
                break

        if device == None:
            error_msg_box("Couldn't connect to the device's bootloader")
            return
        else:
            if self.tryOpenDevice(device): return

            self.program_xusb_boot_firmware_hex(device, file_name)
        self.statusBar().showMessage("Finished updating firmware", timeout=STATUS_BAR_TIMEOUT)

    def program_xusb_boot_firmware_hex(self, device, file_name):
        try:
            xusb_boot.write_hexfile(device, file_name)
        except xusb_boot.BootloaderException as err:
            error_msg_box("Error programming the bootloader to hex file: " + str(err))
        finally:
            device.close()

    def tryOpenDevicePath(self, device_path):
        try:
            device = easyhid.Enumeration().find(path=device_path)[0]
            device.open()
            return device
        except:
            msg_box(
                    description="Failed to open device! Check it is still present "
                    "and you have permission to write to it.",
                    title="USB Device write error"
            )
            return None

    def tryOpenDevice(self, device):
        try:
            device.open()
            return False
        except:
            msg_box(
                    description="Failed to open device! Check it is still present "
                    "and you have permission to write to it.",
                    title="USB Device write error"
            )
            return True

    @Slot(str)
    def resetDeviceHandler(self, device_path):
        device = self.tryOpenDevicePath(device_path)
        if device == None: return

        if is_keyplus_device(device):
            protocol.reset_device(device)
        elif is_xusb_bootloader_device(device):
            xusb_boot.reset(device)
        elif is_nrf24lu1p_bootloader_device(device):
            print("TODO: reset: ", device_path, file=sys.stderr)
        else:
            print("Can't reset device: ", device_path, file=sys.stderr)

    @Slot(str)
    def infoDeviceHandler(self, device_path):
        device = self.tryOpenDevicePath(device_path)
        if device == None: return

        settingsInfo = protocol.get_device_info(device)
        firmwareInfo = protocol.get_firmware_info(device)
        rfInfo = protocol.get_rf_info(device)
        if firmwareInfo.has_at_least_version('0.2.2'):
            errorInfo = protocol.get_error_info(device)
        else:
            errorInfo = None
        device.close()

        def ms_str(x):
            return "{}ms".format(x)

        def us_str(x):
            return "{0:.1f}µs".format(x / 255 * 48.0)

        header = ["Attribute", "Value"]
        device_settings = [
            ("Device ID", settingsInfo.id),
            ("Device name", settingsInfo.device_name_str()),
            ("Device serial number", device.serial_number),
            ("Last layout update", settingsInfo.timestamp_str()),
            ("Default report mode", settingsInfo.default_report_mode_str()),
            ("Matrix scan mode", settingsInfo.scan_mode_str()),
            ("Matrix columns", settingsInfo.col_count),
            ("Matrix rows", settingsInfo.row_count),
            ("Key debounce press time", ms_str(settingsInfo.debounce_time_press)),
            ("Key debounce release time", ms_str(settingsInfo.debounce_time_release)),
            ("Key press trigger time", ms_str(settingsInfo.trigger_time_press)),
            ("Key release trigger time", ms_str(settingsInfo.trigger_time_release)),
            ("Key discharge idle time", us_str(settingsInfo.parasitic_discharge_delay_idle)),
            ("Key discharge debouncing time", us_str(settingsInfo.parasitic_discharge_delay_debouncing)),
            ("Settings stored CRC", hex(settingsInfo.crc)),
            ("Settings computed CRC", hex(settingsInfo.computed_crc)),

            ("USB", not (settingsInfo.has_usb_disabled() or not firmwareInfo.has_fw_support_usb())),
            ("I2C", not (settingsInfo.has_i2c_disabled() or not firmwareInfo.has_fw_support_i2c())),
            ("nRF24 wireless", not (settingsInfo.has_nrf24_disabled() or not firmwareInfo.has_fw_support_nrf24())),
            ("Unifying mouse", not (settingsInfo.has_unifying_mouse_disabled() or not firmwareInfo.has_fw_support_unifying())),
            ("Bluetooth", not (settingsInfo.has_bluetooth_disabled() or not firmwareInfo.has_fw_support_bluetooth())),

            ("RF pipe0", binascii.hexlify(rfInfo.pipe0).decode('ascii')),
            ("RF pipe1", binascii.hexlify(rfInfo.pipe1).decode('ascii')),
            ("RF pipe2", "{:02x}".format(rfInfo.pipe2)),
            ("RF pipe3", "{:02x}".format(rfInfo.pipe3)),
            ("RF pipe4", "{:02x}".format(rfInfo.pipe4)),
            ("RF pipe5", "{:02x}".format(rfInfo.pipe5)),

            ("RF channel", str(rfInfo.channel)),
            ("RF auto retransmit count", str(rfInfo.arc)),
            ("RF data rate", protocol.data_rate_to_str(rfInfo.data_rate)),
        ]

        firmware_settings = [
            ("Firmware version", "{}.{}.{}".format(
                firmwareInfo.version_major, firmwareInfo.version_minor, firmwareInfo.version_patch)),
            ("Firmware build date", str(datetime.datetime.fromtimestamp(firmwareInfo.timestamp))),
            ("Firmware git hash", "{:08x}".format(firmwareInfo.git_hash)),
            ("Layout storage size", firmwareInfo.layout_flash_size),
            ("Bootloader VID", "{:04x}".format(firmwareInfo.bootloader_vid)),
            ("Bootloader PID", "{:04x}".format(firmwareInfo.bootloader_pid)),
            ("Support scanning", firmwareInfo.has_fw_support_scanning()),
            ("Support scanning col to row", firmwareInfo.has_fw_support_scanning_col_row()),
            ("Support scanning row to col", firmwareInfo.has_fw_support_scanning_row_col()),

            ("Media keys", firmwareInfo.has_fw_support_key_media()),
            ("Mouse keys", firmwareInfo.has_fw_support_key_mouse()),
            ("Layer keys", firmwareInfo.has_fw_support_key_layers()),
            ("Sticky keys", firmwareInfo.has_fw_support_key_sticky()),
            ("Tap keys", firmwareInfo.has_fw_support_key_tap()),
            ("Hold keys", firmwareInfo.has_fw_support_key_hold()),

            ("Support 6KRO", firmwareInfo.has_fw_support_6kro()),
            ("Support NKRO", firmwareInfo.has_fw_support_key_hold()),

            ("Support indicator LEDs", firmwareInfo.has_fw_support_led_indicators()),
            ("Support LED backlighting", firmwareInfo.has_fw_support_led_backlighting()),
            ("Support ws2812 LEDs", firmwareInfo.has_fw_support_led_ws2812()),

            ("Support USB", firmwareInfo.has_fw_support_usb()),
            ("Support nRF24 wireless", firmwareInfo.has_fw_support_nrf24()),
            ("Support Unifying", firmwareInfo.has_fw_support_unifying()),
            ("Support I2C", firmwareInfo.has_fw_support_i2c()),
            ("Support Bluetooth", firmwareInfo.has_fw_support_bluetooth()),
        ]

        if errorInfo:
            error_codes = []
            for code in errorInfo.get_error_codes():
                error_codes.append(
                    (errorInfo.error_code_to_name(code), code)
                )
        else:
            error_codes = [('Error codes require firmware version 0.2.2 or greater',)]

        self.info_window = DeviceInformationWindow(
            self,
            header,
            device_settings,
            firmware_settings,
            error_codes,
        )
        self.info_window.setModal(True)
        self.info_window.exec_()

        self.deviceListWidget.updateList()

    def USBUpdate(self):
        self.deviceListWidget.updateList()

    def showAboutDialog(self):
        QMessageBox.about(self, "About keyplus Loader",
"""
The keyplus layout and firmware loader.
""")

    def showHelpDialog(self):
        QMessageBox.about(self, "keyplus Loader Help",
"""
This is the layout and firmware loader for the keyplus keyboard firmware.

The layout files are *.yaml files. For documentation and examples see here: TODO

The rf files are *.yaml files. For documentation and examples see here: TODO

The firmware loader accepts *.hex files. For the latest keyplus firmware see here: TODO

"""
        )



if __name__ == '__main__':
    import xusb_boot
    import easyhid
    import protocol
    # import time

    app = QApplication(sys.argv)
    ex = Loader()
    sys.exit(app.exec_())
