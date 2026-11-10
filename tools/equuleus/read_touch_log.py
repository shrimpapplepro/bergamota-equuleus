#!/usr/bin/env python3
"""Print the touch rows from a saved SHLOG001 window of the Mi 8 Pro."""
import re
import struct
import sys

data = open(sys.argv[1], 'rb').read()
BLOCK = 4096
header = data[:BLOCK]
print('magic', header[:8])
fields = struct.unpack('<14I', header[32:88])
names = ('window_blocks msg_first msg_blocks msg_bytes slot_first slot_blocks slot_count slots_written '
         'uptime_s rounds write_errors gpt_open gpt_last state').split()
info = dict(zip(names, fields))
print({key: info[key] for key in ('uptime_s', 'rounds', 'write_errors', 'state')})
slots = []
for index in range(info['slot_count']):
    start = (info['slot_first'] + index * info['slot_blocks']) * BLOCK
    text = data[start:start + info['slot_blocks'] * BLOCK].decode('latin1')
    stamp = re.search(r'(\d+)s idle=', text)
    slots.append((int(stamp.group(1)) if stamp else -1, text))
slots.sort(key=lambda item: item[0])
print('slot times', slots[0][0], '..', slots[-1][0])
for line in re.split(r'[\0\n]+', slots[-1][1]):
    line = line.strip('\0 ')
    if re.match(r'(FT[1-7E]\b|TCH |RAIL |SWAP |DISPLAY |SMP |m\d d0|CPF|CF|cpufreq)', line) or 'cur' in line and 'top' in line:
        print(line[:260])
message = data[info['msg_first'] * BLOCK:(info['msg_first'] + info['msg_blocks']) * BLOCK].decode('latin1')
for line in message.split('\n'):
    if re.search(r'enchilada-touch|NativeHid|Container corruption', line):
        print(line[:220])
