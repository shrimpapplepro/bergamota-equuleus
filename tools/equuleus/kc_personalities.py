#!/usr/bin/env python3
"""Print the IOKit personalities whose class or matching mention HID event drivers, from __PRELINK_INFO's XML text."""
import re, sys
data = open(sys.argv[1], 'rb').read()
start = data.find(b'<dict><key>_PrelinkInfoDictionary</key>')
if start < 0:
    start = data.find(b'_PrelinkInfoDictionary')
end = data.find(b'</plist>', start)
xml = data[start:end].decode('latin1') if end > 0 else data[start:start + 80000000].decode('latin1')
print('prelink xml bytes', len(xml))
for m in re.finditer(r'<key>IOClass</key><string[^>]*>(IOHIDEventDriver|IOHIDEventService[^<]*|IOHIDInterface|AppleEmbeddedHID[^<]*)</string>', xml):
    s = max(0, m.start() - 900)
    e = min(len(xml), m.end() + 900)
    chunk = re.sub(r'<integer[^>]*>0x([0-9a-f]+)</integer>', r'0x\1', xml[s:e])
    chunk = re.sub(r'<integer[^>]*>(\d+)</integer>', r'\1', chunk)
    chunk = chunk.replace('<key>', ' ').replace('</key>', '=').replace('<string>', '').replace('</string>', ' ')
    print('=' * 20, m.group(1))
    print(chunk[:1900])
