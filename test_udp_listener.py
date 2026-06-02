"""
UDP 监听器（纯 socket，无需 scapy）
监听 UDP :8890 并打印报文信息
板子 → Windows(:8890) → WSL(:8890) 的转发链路测试
"""
import socket
import datetime
import signal
import sys

running = True

def signal_handler(signum, frame):
    global running
    print('\n正在停止监听...', flush=True)
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', 8890))

print(f'UDP 监听器已启动')
print(f'  监听: 0.0.0.0:8890')
print(f'  (Ctrl+C 停止)')
print('=' * 80, flush=True)

packet_count = 0
while running:
    try:
        sock.settimeout(1.0)
        data, addr = sock.recvfrom(65535)
        packet_count += 1
        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        info = f'[{ts}] {addr[0]}:{addr[1]} -> 8890 | len={len(data)}'

        hex_str = data.hex()
        if len(hex_str) > 60:
            hex_preview = hex_str[:60] + '...'
        else:
            hex_preview = hex_str

        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[:40])

        print(f'  [#{packet_count:04d}] {info}', flush=True)
        print(f'           hex: {hex_preview}', flush=True)
        print(f'          ascii: {ascii_str}', flush=True)
        print(f'           raw bytes: {data}', flush=True)
        print('-' * 80, flush=True)

    except socket.timeout:
        continue
    except OSError:
        break

sock.close()
print(f'\n统计: 共接收 {packet_count} 个报文')
print('监听器已停止')
