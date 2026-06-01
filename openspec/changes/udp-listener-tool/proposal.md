## 为什么

需要一个简单的 UDP 监听工具，用于捕获板子发送的 UDP 报文并进行展示或存储。本工具运行在 Windows 上，默认监听 `192.168.1.100:8890`，支持控制台实时展示和 pcap 文件存储两种模式，便于用 Wireshark 回放分析。

## 变更内容

- 新增 `udp_listener.py` — Python 编写的 UDP 监听工具
- 支持两种模式：`console`（默认）和 `pcap`
- IP 和 Port 通过命令行参数可配置，默认 `192.168.1.100:8890`
- 持续监听，Ctrl+C 停止

## 功能 (Capabilities)

### 新增功能

- `udp-listener`: UDP 监听工具，支持控制台展示和 pcap 文件写入

## 影响

- 新增 Python 脚本：`udp_listener.py`
- 依赖：`scapy` 库（用于 UDP 监听和 pcap 写入）