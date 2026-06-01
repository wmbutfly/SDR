## 上下文

在 Windows 环境下运行，需要捕获另一个设备（板子）发送的 UDP 报文。默认监听 `192.168.1.100:8890`，支持两种输出模式。

## 目标 / 非目标

**目标：**
- 绑定指定 IP 和 Port 持续监听 UDP 报文
- `console` 模式：实时打印报文到控制台
- `pcap` 模式：将报文追加写入 pcap 文件，便于 Wireshark 回放
- IP 和 Port 可通过命令行参数配置
- 持续运行，Ctrl+C 终止

**非目标：**
- 不发送 UDP 报文（仅监听）
- 不支持协议解析（仅存储原始报文）
- 不实现复杂的过滤规则

## 决策

### 1. 使用 Scapy 库

**选择：** `scapy`

**理由：**
- 跨平台支持好，Windows 兼容性强
- API 简洁，一行 `sniff()` 即可抓包
- 内置 pcap 写入支持（`wrpcap`）
- 安装简单：`pip install scapy`

### 2. CLI 设计

使用 Python 内置 `argparse`，无额外依赖：

```bash
python udp_listener.py --mode console --ip 192.168.1.100 --port 8890
python udp_listener.py --mode pcap --output capture.pcap
```

### 3. pcap 追加写入

Scapy 的 `wrpcap` 默认是覆盖模式。要实现追加写入，每次捕获后重新 `wrpcap`（追加模式需使用 `append=True`，但 Scapy 不直接支持）。采用**每收到一包立即写入**的方式，使用自定义 Writer 或每次捕获后重新写入。

### 4. 监听地址绑定

使用 `scapy` 的 `sniff()` 配合 `iface` 参数或 `store=False`。Scapy 会自动绑定到指定地址。

## 风险 / 权衡

| 风险 | 缓解措施 |
|------|----------|
| Windows 上需要管理员权限抓包 | 文档说明，需以管理员权限运行 |
| pcap 追加写入复杂 | 使用 `pcapWriter` 类实现追加 |
| 高流量下性能 | 限制 snaplen=65535 |