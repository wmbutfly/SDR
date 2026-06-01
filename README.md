# UDP 监听工具

用于监听 UDP 报文并在控制台展示或保存到 pcap 文件。

## 安装依赖

```bash
pip install scapy
```

**注意**：
- Windows 上需要以**管理员权限**运行
- 需要安装 [Npcap](https://npcap.com/) 驱动（安装时勾选 "WinPcap API-compatible Mode"）

## 使用方法

### 控制台模式（默认）

实时在控制台打印 UDP 报文：

```bash
python udp_listener.py
```

指定 IP 和端口：

```bash
python udp_listener.py --ip 192.168.1.100 --port 8890
```

### PCAP 模式

将 UDP 载荷保存到 pcap 文件（可用 Wireshark 打开）：

```bash
python udp_listener.py --mode pcap --output capture.pcap
```

### 监听时长

默认持续运行，按 Ctrl+C 停止。可指定时长：

```bash
# 监听 5 秒后自动停止
python udp_listener.py --duration 5

# PCAP 模式 + 10 秒
python udp_listener.py --mode pcap --output capture.pcap --duration 10
```

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--ip` | 192.168.1.100 | 绑定的 IP 地址 |
| `--port` | 8890 | 监听端口 |
| `--mode` | console | 输出模式：`console` 或 `pcap` |
| `--output` | capture.pcap | pcap 输出文件路径 |
| `--duration` | 0 | 监听时长（秒），0 表示持续运行 |

## 控制台输出格式

```
[2026-06-01 17:01:52.443] 192.168.1.1:18498 -> 192.168.1.100:8890 | len=260 | 00 00 3c 00 2f 40...
```

- 时间戳
- 源 IP:源端口 -> 目标 IP:目标端口
- UDP 载荷长度
- 载荷数据（十六进制）

## PCAP 文件格式

- linktype = 101 (Raw IP)
- 仅存储 UDP 载荷数据（不包含 IP/UDP 头）
- 每条记录：16 字节 pcap 头 + 载荷数据

## 完整示例

```bash
# 监听并控制台展示
python udp_listener.py --ip 192.168.1.100 --port 8890 --mode console

# 监听并保存 pcap（持续运行）
python udp_listener.py --ip 192.168.1.100 --port 8890 --mode pcap --output board_capture.pcap

# 监听 30 秒并保存 pcap
python udp_listener.py --ip 192.168.1.100 --port 8890 --mode pcap --output capture.pcap --duration 30

# 监听所有接口的 8890 端口
python udp_listener.py --ip 0.0.0.0 --port 8890 --mode console
```

## 注意事项

1. **管理员权限**：Windows 上抓包需要管理员权限
2. **防火墙**：确保防火墙允许 UDP 端口 8890 入站
3. **PYTHONUTF8**：如果中文显示乱码，设置环境变量 `PYTHONUTF8=1`
4. **持续运行**：不指定 `--duration` 时，程序会持续监听直到按 Ctrl+C