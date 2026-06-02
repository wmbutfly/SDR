#!/usr/bin/env python3
"""
UDP 监听 + PCAP 保存（纯 socket，无需 scapy）
接收 UDP :8890 的载荷（802.11 Radiotap 帧），保存到 pcap 文件
"""
import socket
import struct
import os
import signal
import sys
import time
import datetime

PCAP_MAGIC = 0xa1b2c3d4
PCAP_VERSION_MAJOR = 2
PCAP_VERSION_MINOR = 4
LINKTYPE_IEEE802_11_RADIO = 127

running = True

def signal_handler(signum, frame):
    global running
    print('\n正在停止...', flush=True)
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def write_pcap_header(f, snaplen=65535, linktype=LINKTYPE_IEEE802_11_RADIO):
    header = struct.pack('<IHHiIII',
        PCAP_MAGIC,
        PCAP_VERSION_MAJOR,
        PCAP_VERSION_MINOR,
        0, 0,
        snaplen,
        linktype,
    )
    f.write(header)

def write_pcap_packet(f, data, ts=None):
    if ts is None:
        ts = time.time()
    ts_sec = int(ts)
    ts_usec = int((ts - ts_sec) * 1_000_000)
    pkt_header = struct.pack('<IIII',
        ts_sec, ts_usec,
        len(data),
        len(data),
    )
    f.write(pkt_header)
    f.write(data)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', 8890))

pcap_path = '/mnt/c/Users/admin/SDR/udp_capture.pcap'
with open(pcap_path, 'wb') as f:
    write_pcap_header(f)

    print(f'UDP → PCAP 保存器已启动')
    print(f'  监听: 0.0.0.0:8890')
    print(f'  输出: {pcap_path}')
    print(f'  linktype: 127 (802.11 + Radiotap)')
    print(f'  (Ctrl+C 停止)')
    print('=' * 80, flush=True)

    packet_count = 0
    while running:
        try:
            sock.settimeout(1.0)
            data, addr = sock.recvfrom(65535)
            packet_count += 1

            ts = time.time()
            write_pcap_packet(f, data, ts)

            ts_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
            hex_str = data.hex()
            if len(hex_str) > 64:
                hex_preview = hex_str[:64] + '...'
            else:
                hex_preview = hex_str
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[:32])

            print(f'  [#{packet_count:04d}] [{ts_str}] {addr[0]}:8890 → {len(data)}B', flush=True)
            print(f'         hex: {hex_preview}', flush=True)
            print(f'       ascii: {ascii_str}', flush=True)
        except socket.timeout:
            continue
        except OSError:
            break

print(f'\n统计: 共保存 {packet_count} 个报文到 {pcap_path}')
