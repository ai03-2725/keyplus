#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2018 jem@seethis.link
# Licensed under the MIT license (http://opensource.org/licenses/MIT)

from __future__ import absolute_import, division, print_function, unicode_literals

import sys
import easyhid
import struct
import hexdump
import time

from collections import namedtuple
from pprint import pprint

from keyplus.constants import *
from keyplus.usb_ids import is_keyplus_usb_id
from keyplus.error_table import KeyplusErrorTable
import keyplus.exceptions
from keyplus.exceptions import *
from keyplus.device_info import *
import keyplus.io_map

from keyplus.layout import *

from keyplus.debug import DEBUG

from keyplus.cdata_types import layout_settings_t

def _get_similar_serial_number(dev_list, serial_num):
    partial_match = None
    partial_match_pos = None
    for dev in dev_list.find():
        if dev.serial_number == serial_num:
            # found an exact match
            return serial_num
        else:
            # didn't find an exact match, so keep track of partial matches
            match_pos = dev.serial_number.find(serial_num)

            # no match, ignore
            if match_pos == -1:
                continue

            # update the best match we found, prioritize serial_num numbers
            # that match near the start of the string
            if partial_match_pos == None or match_pos < partial_match_pos:
                partial_match = dev.serial_number
                partial_match_pos = match_pos

    if partial_match:
        return partial_match
    else:
        return serial_num

def find_devices(name=None, serial_number=None, vid_pid=None, device_id=None,
                 hid_enumeration=None):
    """
    Returns a list of keyplus keyboards that are currently connected to the
    computer. The arguments can be used to filter result.

    Args:
        name: filter list by the device name
        serial_number: filter list by the devices serial number. Tries for an
            exact match, but will accept a partial match if an exact match is
            not found.
        vid_pid: filter list by the USB vendor and product id for the device in
            the format 'VID:PID'.
        device_id: filter list by device id
        hid_enumeration: an enumeration of USB devices to test. If this argument
            is not set, the function will call `easyhid.Enumeration()` itself.
    """
    if not hid_enumeration:
        hid_enumeration = easyhid.Enumeration()

    target_vid = 0
    target_pid = 0

    if vid_pid:
        matches = vid_pid.split(":")
        if len(matches) == 1:
            try:
                target_vid = int(matches[0], base=16)
            except TypeError:
                KeyplusError("Bad VID/PID pair: " + vid_pid)
        elif len(matches) == 2:
            try:
                if matches[0] == '':
                    target_vid = None
                else:
                    target_vid = target_vid = int(matches[0], base=16)
                if matches[1] == '':
                    target_pid = None
                else:
                    target_pid = target_pid = int(matches[1], base=16)
            except TypeError:
                raise KeyplusError("Bad VID/PID pair: " + vid_pid)

    assert(target_vid <= 0xffff)
    assert(target_pid <= 0xffff)

    if serial_number != None:
        serial_number = _get_similar_serial_number(hid_enumeration, serial_number)

    matching_devices = hid_enumeration.find(
        vid=target_vid,
        pid=target_pid,
        serial=serial_number,
        interface=INTERFACE_VENDOR
    )

    matching_dev_list = []
    for hid_device in matching_devices:
        try:
            if ((target_vid == 0 and target_pid == 0) and
                not is_keyplus_usb_id(hid_device.vendor_id, hid_device.product_id)
            ):
                # Ignore devices that don't use the keyplus vendor IDs
                continue

            new_kb = KeyplusKeyboard(hid_device)
            if device_id != None and device_id != new_kb.get_device_id():
                continue
            if name != None and (name not in new_kb.get_device_name()):
                continue

            matching_dev_list.append(new_kb)
        except (KeyplusError, easyhid.HIDException) as err:
            # Couldn't open the device. Could be in use by another program or
            # do not have correct permissions to read from it.
            print("Warning: couldn't open device: " + str(err), file=sys.stderr)
            hid_device.close()

    return matching_dev_list


class KeyplusKeyboard(object):
    def __init__(self, hid_device):
        self.hid_device = hid_device

        self._layout_data_dirty = True
        self._layout_info_dirty = True
        self._rf_info_dirty = True

        with self.hid_device:
            self.get_device_info()
            self.get_firmware_info()
            self.get_rf_info()

        self._is_connected = False

    def __enter__(self):
        self.connect()

    def __exit__(self, err_type, err_value, traceback):
        self.disconnect()

    def _copy_device_info(self, other):
        """ Copy the internal device information to the object """
        self.hid_device = other.hid_device
        self.device_info = other.device_info
        self.firmware_info = other.firmware_info
        # self.layout_info = other.layout_info

    def get_device_target(self):
        device_target = KeyboardDeviceTarget(
            device_id = self.device_info.device_id,
            firmware_info = self.firmware_info,
        )
        return device_target

    def reconnect(self):
        """ Reconnect to a device after it has been reset.  """
        if self.get_serial_number() not in ["", None]:
            self.hid_device.close()
            new_kb = find_devices(
                serial_number=self.get_serial_number()
            )[0]
            self._copy_device_info(new_kb)
            self.connect()

    def connect(self):
        """ Establish a connection with the keyboard """
        self.hid_device.open()
        self._is_connected = True

    def disconnect(self):
        """ Disconnect a device.  """
        self.hid_device.close()
        self._is_connected = False

###############################################################################
#                                USB Commands                                 #
###############################################################################

    def simple_command(self, cmd_id, cmd_data=None, receive=True, match_data=None):
        """
        Returns:
            The bytes read from the command if `receive` is True

        Raises:
            HIDException, KeyplusProtocolError
        """
        cmd_packet = bytearray(EP_VENDOR_SIZE)
        cmd_packet[0] = cmd_id

        # Optional data component
        if cmd_data != None:
            cmd_data = bytearray(cmd_data)
            if len(cmd_data) > (EP_VENDOR_SIZE-1):
                raise KeyplusProtocolError("Data can't fit in one packet. Got {} "
                    "bytes, max is {}".format(len(cmd_data), EP_VENDOR_SIZE))
            for i, byte in enumerate(cmd_data):
                cmd_packet[i+1] = byte

        self.hid_write(cmd_packet)

        if receive:
            response = self.hid_read()

            packet_type = response[0]

            while packet_type != cmd_id and packet_type != CMD_ERROR_CODE: # ignore other packets
                response = self.hid_read(timeout=1)
                if response == None:
                    self.hid_device.write(cmd_packet)
                else:
                    packet_type = response[0]


            if response[0] == CMD_ERROR_CODE:
                keyplus.exceptions.raise_error_code(response[1])
            elif response[0] != cmd_id:
                raise KeyplusProtocolError("Unexpected packet with packet_id: {}"
                        .format(response[0]))
            return response[1:]
        else:
            return None

    def hid_write(self, data):
        if DEBUG.usb_cmd_timing:
            print("{:.3F} usb sent:".format(time.monotonic()))
            hexdump.hexdump(data)
        self.hid_device.write(data)

    def hid_read(self, timeout=None):
        response = self.hid_device.read(timeout=timeout)
        if DEBUG.usb_cmd_timing:
            if response == None:
                print("{:.3F} usb recv timeout:".format(time.monotonic()))
            else:
                print("{:.3F} usb recv:".format(time.monotonic()))
                hexdump.hexdump(response)
        return response

    def set_passthrough_mode(self, enable):
        """
        Enable or disable passthrough mode. When enabled passthrough mode makes
        the keyboard send it's raw device matrix to the host.
        """
        enable_bit = 0
        if enable:
            enable_bit = 1
        else:
            enable_bit = 0
        response = self.simple_command(
            CMD_SET_PASSTHROUGH_MODE,
            [enable_bit]
        )

    def enter_bootloader(self):
        """ Enter the device's bootloader. """
        response = self.simple_command(
            CMD_BOOTLOADER,
            receive=False
        )
        return (self.firmware_info.bootloader_vid, self.firmware_info.bootloader_pid)

    def enter_pairing_mode(self):
        """ Enter pairing mode for connecting to a unifying mouse """
        response = self.simple_command(
            CMD_UNIFYING_PAIR,
            receive=False
        )
        return response

    def set_indicator_led(self, led_num, state):
        """ Set an indicator LED """
        response = self.simple_command(
            CMD_LED_CONTROL,
            [led_num, state],
            receive=False
        )
        return response

    def get_error_info(device):
        """ Read the error code table from the device. """
        response = self.simple_command(CMD_GET_INFO, [INFO_ERROR_SYSTEM])[1:]
        error_table_data = response[:KeyplusErrorTable.SIZE_ERROR_CODE_TABLE]
        return KeyplusErrorTable(error_table_data)

    def reset(self, reset_type=RESET_TYPE_HARDWARE):
        """
        Reset the keyboard. There are two types of resets:
            * RESET_TYPE_HARDWARE: causes the mcu to reset
            * RESET_TYPE_SOFTWARE: reruns the initilization code without reseting the USB interface
        """
        response = self.simple_command(
            CMD_RESET,
            [reset_type],
            receive=False
        )
        return response

    def listen_raw(self):
        # TODO: better way to interface with this
        while True:
            response = self.hid_device.read()
            if (response[0] == CMD_PRINT):
                length = response[1]
                hexdump.hexdump(bytes(response[2:length+2]))
            else:
                hexdump.hexdump(bytes(response))

    def get_info_cmd(self, info_page_number):
        response = self.simple_command(CMD_GET_INFO, [info_page_number])
        if response[0] == INFO_UNSUPPORTED:
            raise KeyplusUnsupportedError(
                "Device doesn't have any data for info page number '{}'"
                .format(info_page_number)
            )
        if response[0] != info_page_number:
            raise KeyplusProtocolError(
                "Error while getting info from device. "
                "Expected data for info page: {}, but got from {}."
                .format(info_page_number, response[0])
            )
        return response[1:]

    def get_device_info(self):
        DEVICE_INFO_SIZE = 96
        response = self.get_info_cmd(INFO_MAIN_0)
        response += self.get_info_cmd(INFO_MAIN_1)
        response = response[0:DEVICE_INFO_SIZE]

        device_info = KeyboardSettingsInfo()
        device_info.unpack(response)
        self.device_info = device_info
        return device_info

    def get_firmware_info(self):
        response = self.get_info_cmd(INFO_FIRMWARE)
        firmware_info = KeyboardFirmwareInfo()
        firmware_info.unpack(response)
        self.firmware_info = firmware_info
        return firmware_info

    def get_layout_info_header(self):
        response = self.get_info_cmd(INFO_LAYOUT)
        layout_info = KeyboardLayoutInfo()
        layout_info.unpack(response[0:KeyboardLayoutInfo.__size__])
        self.layout_info = layout_info
        return layout_info

    def get_layout_info(self):
        if not self._layout_info_dirty:
            return self.layout_settings

        response = bytearray(0)
        for i in range(INFO_NUM_LAYOUT_DATA_PAGES):
            response = response + self.get_info_cmd(INFO_LAYOUT_DATA_0 + i)

        layout_settings = KeyboardLayoutInfo()

        layout_settings.unpack(response[:layout_settings_t.__size__])
        self.layout_settings = layout_settings
        self._layout_info_dirty = False
        return layout_settings

    def get_rf_info(self):
        if not self._rf_info_dirty:
            return self.rf_info

        response = self.get_info_cmd(INFO_RF)

        rf_info = KeyboardRFInfo()
        rf_info.unpack(response[0:SETTINGS_RF_INFO_HEADER_SIZE] + bytearray(AES_KEY_LEN*2))
        self.rf_info = rf_info
        self._rf_info_dirty = False
        return rf_info

    def read_whole_layout(self):
        if not self._layout_data_dirty:
            return self._whole_layout_data

        start = time.time()
        bytes_remaining = self.firmware_info.layout_flash_size
        offset = 0

        result = bytearray()
        while bytes_remaining != 0:
            bytes_to_read = min(bytes_remaining, 63)
            result += self.read_layout_data(offset, bytes_to_read)
            bytes_remaining -= bytes_to_read
            offset += bytes_to_read

        finish = time.time()
        if DEBUG.usb_cmd_timing:
            print("Time to read layout: ", finish - start)

        self._whole_layout_data = result
        self._layout_data_dirty = False

        return result

    def _get_layout_data_sections(self):
        device_target = self.get_device_target()

        if self.firmware_info.internal_scan_method == MATRIX_SCANNER_INTERNAL_NONE:
            pin_mapping_section = 0
        elif self.firmware_info.internal_scan_method == MATRIX_SCANNER_INTERNAL_FAST_ROW_COL:
            header_size = device_target.get_io_mapper().get_storage_size()
            header_size += MAX_NUM_ROWS
            scan_plan = self.device_info.scan_plan
            map_size = (scan_plan.max_col_pin_num+1) * scan_plan.rows
            pin_mapping_section = header_size + map_size

        data = self._whole_layout_data

        # ekc_size =
        external_keycode_table = pin_mapping_section + struct.unpack(
            "< H",
            data[pin_mapping_section:pin_mapping_section+2],
        )[0]

        pin_map_data = data[:pin_mapping_section]
        ekc_data = data[pin_mapping_section:external_keycode_table]
        layout_data = data[external_keycode_table+2:]

        return (
            pin_map_data,
            ekc_data,
            layout_data
        )

    def _get_layout_keycode_arrays(self, layout_data):
        self.get_layout_info()

        result = []

        pos = 0

        for layout_i in range(self.layout_settings.number_layouts):
            layout = self.layout_settings.layouts[layout_i]
            devices = self.layout_settings.get_layout_device_sizes(layout_i)
            num_layers = self.layout_settings.layouts[layout_i].layer_count
            layout_keycodes = []
            for layer_i in range(num_layers):
                layer = []
                for (offset, size) in devices:
                    keycodes = struct.unpack(
                        "<" + "H" * (size // 2),
                        layout_data[pos:pos+size]
                    )
                    layer.append(list(keycodes))
                    pos += size
                layout_keycodes.append(layer)
            result.append(layout_keycodes)


        return result

    def unpack_layout_data(self):
        self.read_whole_layout()
        device_target = self.get_device_target()

        pin_map_data, ekc_table, layout_data = self._get_layout_data_sections()

        scan_mode = ScanMode()
        pin_mapping = KeyboardPinMapping()
        pin_mapping.unpack(
            pin_map_data,
            self.device_info.scan_plan,
            device_target,
        )
        scan_mode.load_raw_data(self.device_info.scan_plan, pin_mapping)

        # TODO:
        # ekc_table = EKCTable()
        # ekc_table.unpack()
        # hexdump.hexdump(layout_data)

        layout_arrays = self._get_layout_keycode_arrays(layout_data)

        result = []
        for (layout_i, _) in enumerate(layout_arrays):
            layout = LayoutKeyboard(layout_i)
            layout.load_keycodes(layout_arrays[layout_i])
            result.append(layout)

        return result


    def read_layout_data(self, offset, size):
        assert(size <= VENDOR_REPORT_LEN-1)
        control_data = struct.pack("< L B", offset, size)
        return self.simple_command(CMD_READ_LAYOUT, control_data)[:size]

    def get_layers(self, layout_id):
        response = self.simple_command(CMD_GET_LAYER, [layout_id])
        return struct.unpack_from("<B HHH", response)

    def _get_chunks(self, data, chunk_size, pad=0xff):
        chunk_data = None
        remainder = len(data) % chunk_size
        if remainder != 0:
            chunk_data = data[:] + bytearray([pad] * (chunk_size - remainder))
        else:
            chunk_data = data
        return [bytes(chunk_data[i*chunk_size:(i+1)*chunk_size]) for i in range(len(chunk_data)//chunk_size)]

    def _check_cmd_response(self, packet):
        packet_type = packet[0]
        err_code = packet[1]

        if packet_type != CMD_ERROR_CODE:
            raise KeyplusProtocolError(
                "Received unexpected packet type while writing settings "
                "section. Expected {}, but got {} instead."
                .format(CMD_ERROR_CODE, packet_type)
            )
        if err_code != CMD_ERROR_CODE_NONE:
            if err_code in CMD_ERROR_CODE_TABLE:
                err_message = CMD_ERROR_CODE_TABLE[err_code]
            else:
                err_message = "UnknownCmdError({})".format(err_code)
            raise KeyplusProtocolError(
                "USB protocol error: {}".format(err_code)
            )

    def update_settings_section(self, settings_data, keep_rf=0):
        self.simple_command(CMD_UPDATE_SETTINGS, [keep_rf])

        size = SETTINGS_SIZE
        if (keep_rf):
            size = SETTINGS_SIZE - SETTINGS_RF_INFO_SIZE
        chunk_list = self._get_chunks(settings_data[0:size], EP_VENDOR_SIZE)

        for chunk in chunk_list:
            self.hid_write(chunk)
            response = self.hid_read(timeout=3500)
            self._check_cmd_response(response)

    def update_layout_section(self, layout_data):
        chunk_list = self._get_chunks(layout_data, EP_VENDOR_SIZE)

        # TODO: change this to a uint32_t
        num_chunks = struct.pack("<H", len(chunk_list))
        self.simple_command(CMD_UPDATE_LAYOUT, num_chunks)

        for chunk in chunk_list:
            self.hid_write(chunk)
            response = self.hid_read(timeout=3500)
            self._check_cmd_response(response)


if __name__ == '__main__':
    Keyboard()
