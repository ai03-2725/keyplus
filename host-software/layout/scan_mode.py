#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2017 jem@seethis.link
# Licensed under the MIT license (http://opensource.org/licenses/MIT)

from __future__ import absolute_import, division, print_function, unicode_literals

from layout.common import try_get, ParseError
import re, math

MATRIX_SCANNER_MODE_NONE = 0x00 # doesn't have a matrix
MATRIX_SCANNER_MODE_COL_ROW = 0x01 # normal row,col pin matrix
MATRIX_SCANNER_MODE_PINS = 0x02 # each pin represents a key

DEFAULT_DEBOUNCE_PRESS_TIME = 5
DEFAULT_DEBOUNCE_RELEASE_TIME = (2*DEFAULT_DEBOUNCE_PRESS_TIME)
DEFAULT_RELEASE_TRIGGER_TIME = 3
DEFAULT_PRESS_TRIGGER_TIME = 1
DEFAULT_PARASITIC_DISCHARGE_DELAY_IDLE = 2.0
DEFAULT_PARASITIC_DISCHARGE_DELAY_DEBOUNCE = 10.0

class ScanMode:
    COL_ROW = 0
    PINS = 1
    NO_MATRIX = 2
    MODE_MAP = {
        'col_row': COL_ROW,
        'pins': PINS,
        'no_matrix': NO_MATRIX
    }

    def __init__(self, scan_mode_dict, debug_hint):
        self.parse_header(scan_mode_dict, debug_hint)

        if 'matrix_map' in scan_mode_dict:
            self.parse_matrix_map(scan_mode_dict['matrix_map'], debug_hint)
        else:
            self.matrix_map = None

    # uint8_t trigger_time_press; // The key must be down this long before being registered (ms)
    # uint8_t trigger_time_release; // The key must be up this long before being registered (ms)

    # // Both delays are measured on a scale of 0-48µs
    # uint8_t parasitic_discharge_delay_idle; // How long to hold a row low before reading the columns
    # uint8_t parasitic_discharge_delay_debouncing; // How long to hold a row low when a key is debouncing
        if 'debounce_time_press' in scan_mode_dict:
            self.debounce_time_press = scan_mode_dict['debounce_time_press']
        else:
            self.debounce_time_press = DEFAULT_DEBOUNCE_PRESS_TIME

        if 'debounce_time_release' in scan_mode_dict:
            self.debounce_time_release = scan_mode_dict['debounce_time_release']
        else:
            self.debounce_time_release = DEFAULT_DEBOUNCE_RELEASE_TIME

        if 'trigger_time_press' in scan_mode_dict:
            self.trigger_time_press = scan_mode_dict['trigger_time_press']
        else:
            self.trigger_time_press = DEFAULT_PRESS_TRIGGER_TIME

        if 'trigger_time_release' in scan_mode_dict:
            self.trigger_time_release = scan_mode_dict['trigger_time_release']
        else:
            self.trigger_time_release = DEFAULT_RELEASE_TRIGGER_TIME

        if 'parasitic_discharge_delay_idle' in scan_mode_dict:
            delay = scan_mode_dict['parasitic_discharge_delay_idle']
            if (0 < delay > 48.0):
                raise ParseError("parasitic_discharge_delay_idle must less than 48.0µs")
            self.parasitic_discharge_delay_idle = delay
        else:
            self.parasitic_discharge_delay_idle = DEFAULT_PARASITIC_DISCHARGE_DELAY_IDLE

        if 'parasitic_discharge_delay_debouncing' in scan_mode_dict:
            delay = scan_mode_dict['parasitic_discharge_delay_debouncing']
            if (0 < delay > 48.0):
                raise ParseError("parasitic_discharge_delay_debouncing must less than 48.0µs")
            self.parasitic_discharge_delay_debouncing = delay
        else:
            self.parasitic_discharge_delay_debouncing = DEFAULT_PARASITIC_DISCHARGE_DELAY_DEBOUNCE


    def __str__(self):
        if self.mode == ScanMode.NO_MATRIX:
            return "ScanMode(mode=ScanMode.NO_MATRIX)"
        elif self.mode == ScanMode.COL_ROW:
            return "ScanMode(mode=ScanMode.COL_ROW, rows={}, cols={})".format(
                    self.rows, self.cols)

    def parse_header(self, sm_raw, debug_hint):
        self.mode = try_get(sm_raw, 'mode', debug_hint, val_type=str)
        self.mode = ScanMode.MODE_MAP[self.mode]

        self.rows = 0
        self.cols = 0

        if self.mode == ScanMode.COL_ROW:
            self.rows = try_get(sm_raw, 'rows', debug_hint, val_type=int)
            self.cols = try_get(sm_raw, 'cols', debug_hint, val_type=int)
        elif self.mode == ScanMode.PINS:
            # self.rows =
            self.cols = 1
            raise ParseError("pins not implemented")
        else:
            pass # TODO

    def calc_matrix_size(self):
        if self.mode == ScanMode.COL_ROW:
            return int(math.ceil(self.rows * self.cols / 8))
        elif self.mode == ScanMode.PINS:
            return int(math.ceil(self.pin_count / 8))

    def parse_matrix_map(self, mmap_raw, kb_name):
        """ The matrix_map is used to map the keys from how they are "visually
        arranged" to to how they are physically wired. """
        if len(mmap_raw) > self.rows*self.cols:
            raise ParseError("Too many keys in matrix_map for '{}'"
                    "got {} but expected at most {} (={}*{})".format(
                    kb_name, len(mmap_raw), self.rows*self.cols, self.rows, self.cols))
        matrix_map = []
        inverse_map = [0xff] * self.rows * self.cols
        for (key_pos, map_key) in enumerate(mmap_raw):
            # these values can be used as spaces and are ignored
            if map_key in ['none', '_'*4, '_'*5, '_'*6, '-'*4, '-'*5, '-'*6]:
                continue

            r, c = None, None
            try:
                results = re.match('r(\d+)c(\d+)', map_key)
                if results == None:
                    raise ParseError
                r, c = results.groups()
                r, c = int(r), int(c)
            except (ParseError, TypeError):
                raise ParseError("Expected string of the form rXcY, but got '{}' "
                        "in matrix_map '{}'".format(map_key, kb_name))
            key_num = self.cols*r + c
            if r >= self.rows or c >= self.cols:
                raise ParseError("Key remap {} out of bounds "
                "rows={}, cols={} in device matrix_map '{}'".format(map_key, self.rows, self.cols, kb_name))

            if key_num in matrix_map:
                raise ParseError("The key '{}' appears twice in the matrix_map "
                "of '{}'".format(map_key, kb_name))
            matrix_map.append(key_num)
            inverse_map[key_num] = key_pos

        self.matrix_map = matrix_map
        self.inverse_map = inverse_map
