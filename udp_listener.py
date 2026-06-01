#!/usr/bin/env python3
"""
UDP 监听工具

监听 UDP 报文并在控制台展示或保存到 pcap 文件。
用法: python udp_listener.py [--ip IP] [--port PORT] [--mode MODE] [--output FILE]
"""

import argparse
import signal
import sys
import time
from datetime import datetime

# Scapy 库用于网络抓包
from scapy.all import sniff, UDP, IP, wrpcap, Raw
from scapy.compat import raw


class PcapAppendWriter:
    """PCAP 文件写入器，支持追加写入报文"""

    def __init__(self, filename, snaplen=65535, linktype=1):
        self.filename = filename
        self.snaplen = snaplen
        self.linktype = linktype
        self.first_packet = True
        self.packet_count = 0

        # 以追加二进制模式打开文件
        self.f = open(filename, 'ab')
        self._write_file_header_if_needed()

    def _write_file_header_if_needed(self):
        """如果文件为空，写入 PCAP 全局文件头"""
        import os
        if os.path.getsize(self.filename) == 0:
            self._write_file_header()
        else:
            self.first_packet = False

    def _write_file_header(self):
        """写入 24 字节的 PCAP 全局文件头"""
        import struct

        # PCAP 全局文件头 (小端序)
        magic = 0xa1b2c3d4
        version_major = 2
        version_minor = 4
        thiszone = 0
        sigfigs = 0
        snaplen = self.snaplen
        linktype = self.linktype

        header = struct.pack(
            '<IHHiIII',
            magic,
            version_major,
            version_minor,
            thiszone,
            sigfigs,
            snaplen,
            linktype
        )
        self.f.write(header)

    def write_packet(self, packet):
        """将单个报文写入 PCAP 文件"""
        import struct

        # 获取报文原始字节
        pkt_bytes = bytes(packet)

        # 时间戳（秒和微秒）
        ts_sec = int(packet.time)
        ts_usec = int((packet.time - ts_sec) * 1000000)

        # 长度信息
        incl_len = len(pkt_bytes)
        orig_len = incl_len

        # 报文记录头 (16 字节) + 报文数据
        pkt_header = struct.pack('<IIII', ts_sec, ts_usec, incl_len, orig_len)
        self.f.write(pkt_header)
        self.f.write(pkt_bytes)

        self.packet_count += 1

    def close(self):
        """关闭文件句柄"""
        if self.f:
            self.f.close()
            self.f = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class UDPListener:
    """UDP 监听器，支持控制台展示和 pcap 写入两种模式"""

    def __init__(self, ip='192.168.1.100', port=8890, mode='console', output=None):
        self.ip = ip
        self.port = port
        self.mode = mode
        self.output = output
        self.packet_count = 0
        self.running = False
        self.writer = None

        # 设置信号处理器以实现优雅退出
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """处理 Ctrl+C 信号，实现优雅退出"""
        print("\n\n接收到中断信号，正在关闭...")
        self.running = False

    def _print_packet(self, packet):
        """在控制台打印报文信息"""
        if IP in packet and UDP in packet:
            src_ip = packet[IP].src
            dst_ip = packet[IP].dst
            src_port = packet[UDP].sport
            dst_port = packet[UDP].dport

            # 获取载荷数据
            if Raw in packet:
                payload = bytes(packet[Raw].load)
                payload_preview = payload[:32] if len(payload) > 32 else payload
                payload_str = ' '.join(f'{b:02x}' for b in payload_preview)
                if len(payload) > 32:
                    payload_str += '...'
            else:
                payload_str = '(empty)'

            # 获取 UDP 报文长度
            udp_len = packet[UDP].len
            if udp_len is None:
                udp_len = len(packet[UDP].payload) + 8  # 头部 + 载荷

            # 格式化时间戳
            ts = datetime.fromtimestamp(packet.time)
            ts_str = ts.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(ts.microsecond/1000):03d}'

            print(f"[{ts_str}] {src_ip}:{src_port} -> {dst_ip}:{dst_port} | len={udp_len} | {payload_str}")

    def _process_packet(self, packet):
        """处理每个捕获的报文"""
        self.packet_count += 1

        if self.mode == 'console':
            self._print_packet(packet)
        elif self.mode == 'pcap' and self.writer:
            self.writer.write_packet(packet)
            # 每 100 个报文打印一次进度
            if self.packet_count % 100 == 0:
                print(f"已捕获 {self.packet_count} 个报文...")

    def start(self):
        """开始监听 UDP 报文"""
        self.running = True

        # 构造 BPF 过滤器，只捕获发往指定端口的 UDP 报文
        filter_str = f"udp and port {self.port}"

        print(f"正在启动 UDP 监听器...")
        print(f"  IP: {self.ip}")
        print(f"  端口: {self.port}")
        print(f"  模式: {self.mode}")
        if self.mode == 'pcap':
            print(f"  输出文件: {self.output}")
        print(f"\n正在监听 UDP 报文... (按 Ctrl+C 停止)")
        print("-" * 80)

        # 如果是 pcap 模式，初始化写入器
        if self.mode == 'pcap':
            self.writer = PcapAppendWriter(self.output)
            print(f"正在写入 pcap 文件: {self.output}")

        try:
            # 找到对应的网络接口
            from scapy.all import get_if_list, get_if_addr
            target_iface = None
            for iface in get_if_list():
                try:
                    if get_if_addr(iface) == self.ip:
                        target_iface = iface
                        break
                except:
                    pass

            if target_iface:
                print(f"使用网络接口: {target_iface}")

            # 开始抓包
            sniff(
                iface=target_iface,
                filter=filter_str,
                prn=self._process_packet,
                store=False,
                stop_filter=lambda _: not self.running
            )
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def _cleanup(self):
        """清理资源"""
        self.running = False
        if self.writer:
            self.writer.close()
            self.writer = None

        print("-" * 80)
        print(f"\n统计: 共捕获 {self.packet_count} 个报文")
        print("监听器已停止")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='UDP 监听工具 - 监听 UDP 报文并在控制台展示或保存到 pcap 文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python udp_listener.py                                    # 默认控制台模式
  python udp_listener.py --mode console --ip 192.168.1.100   # 自定义 IP
  python udp_listener.py --mode pcap --output capture.pcap   # 保存到 pcap 文件
  python udp_listener.py --ip 0.0.0.0 --port 8891            # 自定义端口
        '''
    )

    parser.add_argument(
        '--ip',
        type=str,
        default='192.168.1.100',
        help='绑定的 IP 地址 (默认: 192.168.1.100)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8890,
        help='监听端口 (默认: 8890)'
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['console', 'pcap'],
        default='console',
        help='输出模式: console 或 pcap (默认: console)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default='capture.pcap',
        help='pcap 输出文件路径 (pcap 模式必需)'
    )

    args = parser.parse_args()

    # 验证 pcap 模式必须指定输出文件
    if args.mode == 'pcap' and not args.output:
        parser.error("pcap 模式必须指定 --output 参数")

    return args


def main():
    """主入口"""
    args = parse_args()

    listener = UDPListener(
        ip=args.ip,
        port=args.port,
        mode=args.mode,
        output=args.output
    )

    listener.start()


if __name__ == '__main__':
    main()