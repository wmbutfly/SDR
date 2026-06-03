#!/usr/bin/env python3
"""
UDP 监听 + PCAP 保存（纯 socket，无需 scapy）
接收 UDP :8890 的载荷（802.11 Radiotap 帧），保存到 pcap 文件
"""
import argparse
import socket
import struct
import os
import signal
import sys
import time
import datetime
import subprocess
import json


PCAP_MAGIC = 0xa1b2c3d4
PCAP_VERSION_MAJOR = 2
PCAP_VERSION_MINOR = 4

# PCAP linktype 常量
LINKTYPE_IEEE802_11_RADIO = 127
LINKTYPE_BLUETOOTH_LE_LL = 251
LINKTYPE_BLUETOOTH_LE_LL_WITH_PHDR = 256

# type 名称 → linktype 映射
TYPE_LINKTYPE = {
    'wifi': LINKTYPE_IEEE802_11_RADIO,
    'ble': LINKTYPE_BLUETOOTH_LE_LL,
    'ble_phdr': LINKTYPE_BLUETOOTH_LE_LL_WITH_PHDR,
}

# type 名称 → 描述
TYPE_DESC = {
    'wifi': '802.11 + Radiotap',
    'ble': 'Bluetooth LE LL',
    'ble_phdr': 'Bluetooth LE LL + PHDR',
}

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

def parse_args():
    parser = argparse.ArgumentParser(description='UDP 监听 + PCAP 保存')
    parser.add_argument('--ip', type=str, default='0.0.0.0',
                        help='监听 IP (默认: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8890,
                        help='监听端口 (默认: 8890)')
    parser.add_argument('--type', '-t', type=str, default='wifi',
                        choices=list(TYPE_LINKTYPE.keys()),
                        help='数据类型，决定 pcap linktype 和文件名 (默认: wifi)')
    parser.add_argument('--linktype', type=int, default=None,
                        help='强制指定 pcap linktype，覆盖 --type 的自动选择')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='输出目录，不存在则自动创建。不指定则用当前目录')
    parser.add_argument('--max-size', '-s', type=str, default='1M',
                        help='单文件上限，超限自动滚动 (默认: 1M)')
    parser.add_argument('--max-files', '-n', type=int, default=0,
                        help='总文件数上限，超限删最老 (默认: 0=不限)')
    parser.add_argument('--max-total', '-m', type=str, default='1G',
                        help='总磁盘占用上限，超限删最老 (默认: 1G)')
    parser.add_argument('--mqtt-host', type=str, default='localhost',
                        help='MQTT broker 地址 (默认: localhost)')
    parser.add_argument('--mqtt-port', type=int, default=1883,
                        help='MQTT broker 端口 (默认: 1883)')
    parser.add_argument('--mqtt-topic', type=str, default='FromSDR',
                        help='MQTT 主题 (默认: FromSDR)')
    parser.add_argument('--mqtt-user', type=str, default='admin',
                        help='MQTT 用户名 (默认: admin)')
    parser.add_argument('--mqtt-password', type=str, default='123456',
                        help='MQTT 密码 (默认: 123456)')
    parser.add_argument('--mqtt-qos', type=int, default=1, choices=[0, 1, 2],
                        help='MQTT QoS 级别 (默认: 1)')
    parser.add_argument('--channel', '-c', type=str, default='1',
                        help='WiFi 信道号，逗号分隔多信道，用于 MQTT 通知 (默认: 1)')
    return parser.parse_args()


def parse_size(val):
    val = val.strip().upper()
    if val.endswith('G'):
        return int(float(val[:-1]) * 1024**3)
    if val.endswith('M'):
        return int(float(val[:-1]) * 1024**2)
    if val.endswith('K'):
        return int(float(val[:-1]) * 1024)
    return int(val)




def trim_old_files(directory, prefix, max_files):
    if max_files <= 0:
        return
    files = [f for f in os.listdir(directory)
             if f.startswith(prefix) and f.endswith('.pcap')]
    if len(files) <= max_files:
        return
    files.sort()
    for old in files[:len(files) - max_files]:
        path = os.path.join(directory, old)
        try:
            os.remove(path)
        except OSError:
            pass


def trim_total_size(directory, prefix, max_bytes):
    if max_bytes <= 0:
        return
    files = []
    total = 0
    for f in os.listdir(directory):
        if not f.startswith(prefix) or not f.endswith('.pcap'):
            continue
        path = os.path.join(directory, f)
        try:
            sz = os.path.getsize(path)
            files.append((f, sz))
            total += sz
        except OSError:
            pass
    if total <= max_bytes:
        return
    files.sort(key=lambda x: x[0])
    for fname, sz in files:
        if total <= max_bytes:
            break
        path = os.path.join(directory, fname)
        try:
            os.remove(path)
            total -= sz
        except OSError:
            pass


def mqtt_publish(host, port, topic, user, password, payload, qos=0, retain=False):
    try:
        cmd = ['mosquitto_pub',
               '-h', host,
               '-p', str(port),
               '-t', topic,
               '-u', user,
               '-P', password,
               '-m', payload,
               '-q', str(qos)]
        if retain:
            cmd.append('-r')
        subprocess.run(cmd, capture_output=True, timeout=5)
    except Exception as e:
        print(f'  [MQTT 失败] {e}', flush=True)


def main():
    args = parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.ip, args.port))

    out_dir = args.output if args.output else '.'
    os.makedirs(out_dir, exist_ok=True)

    linktype = args.linktype if args.linktype is not None else TYPE_LINKTYPE[args.type]
    type_desc = TYPE_DESC.get(args.type, f'linktype={linktype}')

    ts_start = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    pcap_path = os.path.join(out_dir, f'{args.type}_{ts_start}.pcap')
    max_size = parse_size(args.max_size)
    max_total = parse_size(args.max_total)
    total_packets = 0
    roll_count = 0

    f = open(pcap_path, 'wb')
    write_pcap_header(f, linktype=linktype)

    # MQTT 启动通知
    start_payload = json.dumps({'op': 'start', 'mod': args.type, 'channel': args.channel})
    mqtt_publish(args.mqtt_host, args.mqtt_port, args.mqtt_topic,
                 args.mqtt_user, args.mqtt_password, start_payload,
                 args.mqtt_qos, retain=True)

    print(f'UDP → PCAP 保存器已启动')
    print(f'  监听: {args.ip}:{args.port}')
    print(f'  输出目录: {os.path.abspath(out_dir)}')
    print(f'  当前文件: {os.path.basename(pcap_path)}')
    print(f'  类型: {args.type} ({type_desc})')
    print(f'  max-size: {args.max_size}')
    if max_total > 0:
        print(f'  总空间上限: {args.max_total}')
    if args.max_files > 0:
        print(f'  总文件上限: {args.max_files} 个')
    print(f'  MQTT: {args.mqtt_host}:{args.mqtt_port} topic={args.mqtt_topic}')
    print(f'  (Ctrl+C 停止)')
    print('=' * 80, flush=True)

    while running:
        try:
            sock.settimeout(1.0)
            data, addr = sock.recvfrom(65535)
            total_packets += 1

            ts = time.time()
            write_pcap_packet(f, data, ts)

            ts_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
            hex_str = data.hex()
            if len(hex_str) > 64:
                hex_preview = hex_str[:64] + '...'
            else:
                hex_preview = hex_str
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[:32])

            print(f'  [#{total_packets:04d}] [{ts_str}] {addr[0]}:{args.port} → {len(data)}B', flush=True)
            print(f'         hex: {hex_preview}', flush=True)
            print(f'       ascii: {ascii_str}', flush=True)

            if max_size > 0 and f.tell() > max_size:
                f.close()

                roll_count += 1
                ts_now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                prefix = f'{args.type}_'
                new_name = f'{prefix}{ts_now}_{roll_count:03d}.pcap'
                new_path = os.path.join(out_dir, new_name)
                if args.max_files > 0:
                    trim_old_files(out_dir, prefix, args.max_files - 1)
                if max_total > 0:
                    trim_total_size(out_dir, prefix, max_total)
                pcap_path = new_path

                f = open(pcap_path, 'wb')
                write_pcap_header(f, linktype=linktype)
                print(f'  --- 滚动: {os.path.basename(pcap_path)} ---', flush=True)
        except socket.timeout:
            continue
        except OSError:
            break

    f.close()

    stop_payload = json.dumps({'op': 'stop'})
    mqtt_publish(args.mqtt_host, args.mqtt_port, args.mqtt_topic,
                 args.mqtt_user, args.mqtt_password, stop_payload,
                 args.mqtt_qos, retain=True)

    print(f'\n统计: 共保存 {total_packets} 个报文')
    print(f'  输出目录: {os.path.abspath(out_dir)}')


if __name__ == '__main__':
    main()
