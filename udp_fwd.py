"""
Windows → WSL UDP 转发器
监听 192.168.1.100:8890 并将 UDP 数据转发到 WSL 的 172.21.38.252:8890
用于在 WSL 中测试接收板子的 UDP 数据
"""
import socket
import threading
import signal
import sys
import time

WSL_IP = '172.21.38.252'
LOCAL_PORT = 8890
WSL_PORT = 8890

running = True

def signal_handler(signum, frame):
    global running
    print('\n正在停止转发...', flush=True)
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', LOCAL_PORT))

print(f'UDP 转发器已启动')
print(f'  监听: 0.0.0.0:{LOCAL_PORT}')
print(f'  转发 → {WSL_IP}:{WSL_PORT}')
print(f'  (Ctrl+C 停止)')
print('-' * 50, flush=True)

packet_count = 0
while running:
    try:
        sock.settimeout(1.0)
        data, addr = sock.recvfrom(65535)
        packet_count += 1
        print(f'  [#{packet_count}] {addr[0]}:{addr[1]} → WSL ({len(data)} bytes)', flush=True)
        sock.sendto(data, (WSL_IP, WSL_PORT))
    except socket.timeout:
        continue
    except OSError:
        break

sock.close()
print(f'\n转发结束，共转发 {packet_count} 个报文')
