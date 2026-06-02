#!/usr/bin/env python3
"""
UDP 监听工具 (Ubuntu / Linux)

监听 UDP 报文并在控制台展示或保存到 pcap 文件。

平台差异说明（与 Windows 版本相比）：
  - 不需要 Npcap / WinPcap；Linux 内置 libpcap。
  - 需要 root 权限或 CAP_NET_RAW capability：
        sudo python3 udp_listener.py ...
        # 或者一次设置 capability（无需 sudo 每次输入密码）：
        sudo setcap cap_net_raw+ep $(which python3)
  - 默认使用 UTF-8 终端，无需设置 PYTHONUTF8。
  - 网络接口命名不同（eth0 / wlan0 / enp0s3 等），可显式用 --iface 指定。

用法: python3 udp_listener.py [--ip IP] [--port PORT] [--mode MODE] [--output FILE]
                              [--iface IFACE] [--linktype N] [--duration SEC]
"""

import argparse
import os
import signal
import struct
import sys
import threading
import time
from datetime import datetime

# Scapy 库用于网络抓包
from scapy.all import UDP, IP, Raw, get_if_addr, get_if_list, sniff, wrpcap
from scapy.compat import raw  # noqa: F401  (保留以兼容旧代码引用)


# 全局停止事件
stop_event = threading.Event()


def signal_handler(signum, frame):
    """处理 Ctrl+C / SIGTERM 信号，实现优雅退出"""
    print("\n\n接收到中断信号，正在关闭...", file=sys.stderr, flush=True)
    stop_event.set()


# 注册信号处理器
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# PCAP linktype 常量
LINKTYPE_ETHERNET = 1
LINKTYPE_RAW = 101           # Raw IP（仅 IP 头，无以太网头）
LINKTYPE_IEEE802_11 = 105    # 802.11 (无 Radiotap 头)
LINKTYPE_IEEE802_11_RADIO = 127  # 802.11 + Radiotap 头


class PcapAppendWriter:
    """PCAP 文件写入器，支持追加写入报文。

    仅存储 UDP 载荷数据。linktype 描述载荷的链路层类型，常见取值：
        1   = LINKTYPE_ETHERNET
        101 = LINKTYPE_RAW            （裸 IP）
        105 = LINKTYPE_IEEE802_11
        127 = LINKTYPE_IEEE802_11_RADIO（802.11 + Radiotap）
    """

    def __init__(self, filename, snaplen=65535, linktype=LINKTYPE_IEEE802_11_RADIO):
        self.filename = filename
        self.snaplen = snaplen
        self.linktype = linktype
        self.packet_count = 0
        self.first_packet = True

        # 以追加二进制模式打开文件
        self.f = open(filename, 'ab')
        self._write_file_header_if_needed()

    def _write_file_header_if_needed(self):
        """如果文件为空，写入 PCAP 全局文件头"""
        if os.path.getsize(self.filename) == 0:
            self._write_file_header()
        else:
            self.first_packet = False

    def _write_file_header(self):
        """写入 24 字节的 PCAP 全局文件头（小端序）"""
        magic = 0xa1b2c3d4
        version_major = 2
        version_minor = 4
        thiszone = 0
        sigfigs = 0
        header = struct.pack(
            '<IHHiIII',
            magic,
            version_major,
            version_minor,
            thiszone,
            sigfigs,
            self.snaplen,
            self.linktype,
        )
        self.f.write(header)

    def write_packet(self, packet):
        """将 UDP 载荷写入 PCAP 文件。"""
        if UDP not in packet:
            return

        payload = bytes(packet[UDP].payload)
        if len(payload) == 0:
            return

        # 时间戳（秒和微秒）
        ts_sec = int(packet.time)
        ts_usec = int((packet.time - ts_sec) * 1_000_000)

        # 报文记录头 (16 字节) + 载荷数据
        pkt_header = struct.pack(
            '<IIII',
            ts_sec,
            ts_usec,
            len(payload),  # incl_len
            len(payload),  # orig_len
        )
        self.f.write(pkt_header)
        self.f.write(payload)

        self.packet_count += 1
        self.first_packet = False

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


def check_capture_privileges(iface: str | None) -> None:
    """Linux 抓包需要 root 或 CAP_NET_RAW；提前给出明确错误。"""
    if os.geteuid() == 0:
        return

    # 退而求其次：通过 /proc/self/status 检查 capability 位
    try:
        with open('/proc/self/status') as fh:
            for line in fh:
                if line.startswith('CapEff:'):
                    cap_eff = int(line.split()[1], 16)
                    if cap_eff & (1 << 13):  # CAP_NET_RAW
                        return
                    break
    except OSError:
        pass

    print("错误: 需要 root 权限或 CAP_NET_RAW capability 才能抓包。", file=sys.stderr)
    print("  方法 1: sudo python3 udp_listener.py ...", file=sys.stderr)
    print("  方法 2: sudo setcap cap_net_raw+ep $(which python3)", file=sys.stderr)
    if iface:
        print(f"  （目标接口: {iface}）", file=sys.stderr)
    sys.exit(1)


def resolve_interface(target_ip: str | None, iface: str | None) -> str | None:
    """解析实际使用的网络接口。

    优先级:
      1. 显式 --iface
      2. 通过 --ip 在本机接口列表中匹配
      3. 通过默认路由找到出接口
      4. None（抓包库自行选择，通常是 any）
    """
    if iface:
        return iface

    interfaces = get_if_list()
    if target_ip and target_ip not in ('0.0.0.0',):
        for name in interfaces:
            try:
                if get_if_addr(name) == target_ip:
                    return name
            except Exception:
                continue

    # 尝试通过默认路由推断
    try:
        from scapy.route import Route
        route = Route()
        default_iface, _, _ = route.route('0.0.0.0')
        if default_iface and default_iface in interfaces:
            return default_iface
    except Exception:
        pass

    return None


class UDPListener:
    """UDP 监听器，支持控制台展示和 pcap 写入两种模式"""

    def __init__(self, ip='0.0.0.0', port=8890, mode='console', output=None,
                 duration=0, iface=None, linktype=LINKTYPE_IEEE802_11_RADIO):
        self.ip = ip
        self.port = port
        self.mode = mode
        self.output = output
        self.duration = duration  # 0 表示持续运行
        self.iface = iface
        self.linktype = linktype
        self.packet_count = 0
        self.running = False
        self.writer = None

    def _print_packet(self, packet):
        """在控制台打印报文信息"""
        if IP in packet and UDP in packet:
            src_ip = packet[IP].src
            dst_ip = packet[IP].dst
            src_port = packet[UDP].sport
            dst_port = packet[UDP].dport

            # UDP 载荷（与 pcap 模式一致）
            payload = bytes(packet[UDP].payload)
            payload_len = len(payload)

            # 格式化时间戳
            ts = datetime.fromtimestamp(packet.time)
            ts_str = ts.strftime('%Y-%m-%d %H:%M:%S') + f'.{ts.microsecond // 1000:03d}'

            print(
                f'[{ts_str}] {src_ip}:{src_port} -> {dst_ip}:{dst_port} '
                f'| len={payload_len} | {payload.hex()}',
                flush=True,
            )

    def _process_packet(self, packet):
        """处理每个捕获的报文"""
        self.packet_count += 1

        if self.mode == 'console':
            self._print_packet(packet)
        elif self.mode == 'pcap' and self.writer:
            self.writer.write_packet(packet)
            # 每 100 个报文打印一次进度
            if self.packet_count % 100 == 0:
                print(f"已捕获 {self.packet_count} 个报文...", flush=True)

    def start(self):
        """开始监听 UDP 报文"""
        self.packet_count = 0

        # 构造 BPF 过滤器，只捕获发往指定端口的 UDP 报文
        filter_str = f"udp and port {self.port}"

        # 解析实际接口
        target_iface = resolve_interface(self.ip, self.iface)

        print("正在启动 UDP 监听器...", flush=True)
        print(f"  IP: {self.ip}", flush=True)
        print(f"  端口: {self.port}", flush=True)
        print(f"  模式: {self.mode}", flush=True)
        if self.mode == 'pcap':
            print(f"  输出文件: {self.output}", flush=True)
            print(f"  PCAP linktype: {self.linktype}", flush=True)
        if target_iface:
            print(f"  网络接口: {target_iface}", flush=True)
        else:
            print("  网络接口: <auto>（未指定，按 scapy 默认）", flush=True)
        print("\n正在监听 UDP 报文... (按 Ctrl+C 停止)", flush=True)
        print("-" * 80, flush=True)

        # 权限检查
        check_capture_privileges(target_iface)

        # 如果是 pcap 模式，初始化写入器
        if self.mode == 'pcap':
            self.writer = PcapAppendWriter(self.output, linktype=self.linktype)
            print(f"正在写入 pcap 文件: {self.output}", flush=True)

        # 重置停止事件
        stop_event.clear()

        try:
            sniff_kwargs = {
                'iface': target_iface,
                'filter': filter_str,
                'prn': self._process_packet,
                'store': False,
                'stop_filter': lambda _: stop_event.is_set(),
            }
            if self.duration > 0:
                print(f"监听时长: {self.duration} 秒", flush=True)
                sniff_kwargs['timeout'] = self.duration + 1

            sniff(**sniff_kwargs)
        except KeyboardInterrupt:
            pass
        except OSError as e:
            # 典型错误：权限不足、接口不存在
            print(f"\n抓包失败: {e}", file=sys.stderr)
            print("  确认: 1) 以 root 运行或设置 CAP_NET_RAW", file=sys.stderr)
            print("        2) --iface 指定的网络接口存在", file=sys.stderr)
            print("        3) 端口正确且没有防火墙拦截", file=sys.stderr)
            sys.exit(1)
        finally:
            self._cleanup()

    def _cleanup(self):
        """清理资源"""
        self.running = False
        if self.writer:
            self.writer.close()
            self.writer = None

        print("-" * 80, flush=True)
        print(f"\n统计: 共捕获 {self.packet_count} 个报文", flush=True)
        print("监听器已停止", flush=True)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='UDP 监听工具 (Ubuntu/Linux) - 监听 UDP 报文并在控制台展示或保存到 pcap 文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 控制台模式（默认），按 IP 自动选接口
  sudo python3 udp_listener.py --ip 192.168.1.100 --port 8890

  # 显式指定网络接口
  sudo python3 udp_listener.py --iface wlan0 --port 8890

  # 保存到 pcap 文件（用 Wireshark 打开）
  sudo python3 udp_listener.py --ip 192.168.1.100 --port 8890 \\
      --mode pcap --output capture.pcap

  # 监听 5 秒后自动停止
  sudo python3 udp_listener.py --ip 192.168.1.100 --port 8890 --duration 5
        ''',
    )

    parser.add_argument(
        '--ip', type=str, default='0.0.0.0',
        help='绑定的 IP 地址（用于自动选择接口）。0.0.0.0 表示不限制 (默认: 0.0.0.0)',
    )
    parser.add_argument(
        '--port', type=int, default=8890,
        help='监听端口 (默认: 8890)',
    )
    parser.add_argument(
        '--mode', type=str, choices=['console', 'pcap'], default='console',
        help='输出模式: console 或 pcap (默认: console)',
    )
    parser.add_argument(
        '--output', type=str, default='capture.pcap',
        help='pcap 输出文件路径（pcap 模式使用）(默认: capture.pcap)',
    )
    parser.add_argument(
        '--duration', type=int, default=0,
        help='监听时长（秒），0 表示持续运行 (默认: 0)',
    )
    parser.add_argument(
        '--iface', type=str, default=None,
        help='显式指定网络接口（如 wlan0 / eth0 / any）。'
             '未指定时根据 --ip 或默认路由自动选择',
    )
    parser.add_argument(
        '--linktype', type=int, default=LINKTYPE_IEEE802_11_RADIO,
        help=f'PCAP 链路类型（仅 pcap 模式）。常见: '
             f'1=以太网, 101=Raw IP, 105=802.11, 127=802.11+Radiotap (默认: 127)',
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
        output=args.output,
        duration=args.duration,
        iface=args.iface,
        linktype=args.linktype,
    )

    listener.start()


if __name__ == '__main__':
    main()
