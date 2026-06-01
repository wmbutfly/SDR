#!/usr/bin/env python3
"""
UDP 测试发送工具

用于发送 UDP 测试报文，方便测试 udp_listener.py
用法: python send_udp_test.py [--ip IP] [--port PORT] [--count COUNT]
"""

import socket
import time
import random

def send_udp_test(target_ip='192.168.1.100', target_port=8890, count=1, interval=0.5):
    """
    发送 UDP 测试报文

    Args:
        target_ip: 目标 IP 地址
        target_port: 目标端口
        count: 发送报文数量
        interval: 报文间隔（秒）
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"正在向 {target_ip}:{target_port} 发送 {count} 个 UDP 报文")

    for i in range(count):
        # 生成随机载荷数据
        payload = bytes([random.randint(0, 255) for _ in range(16)])
        sock.sendto(payload, (target_ip, target_port))
        print(f"  已发送报文 {i+1}: {' '.join(f'{b:02x}' for b in payload)}")
        time.sleep(interval)

    sock.close()
    print("发送完成")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='发送 UDP 测试报文')

    parser.add_argument(
        '--ip',
        default='192.168.1.100',
        help='目标 IP 地址 (默认: 192.168.1.100)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8890,
        help='目标端口 (默认: 8890)'
    )

    parser.add_argument(
        '--count',
        type=int,
        default=3,
        help='发送报文数量 (默认: 3)'
    )

    parser.add_argument(
        '--interval',
        type=float,
        default=0.5,
        help='报文间隔，秒 (默认: 0.5)'
    )

    args = parser.parse_args()
    send_udp_test(args.ip, args.port, args.count, args.interval)