## 1. 环境准备

- [x] 1.1 创建 `udp_listener.py` 文件
- [x] 1.2 添加 `scapy` 依赖说明（安装命令）

## 2. 核心实现

- [x] 2.1 实现命令行参数解析（argparse）
  - `--ip` 默认 `192.168.1.100`
  - `--port` 默认 `8890`
  - `--mode` 默认 `console`
  - `--output` pcap 输出文件

- [x] 2.2 实现 `console` 模式：实时打印 UDP 报文
  - 时间戳格式：`[YYYY-MM-DD HH:MM:SS.mmm]`
  - 打印内容：`SRC_IP:SRC_PORT -> DST_IP:DST_PORT | 长度 | Payload预览`

- [x] 2.3 实现 `pcap` 模式：追加写入 pcap 文件
  - 创建有效的 pcap 文件头
  - 每收到一包追加写入

- [x] 2.4 实现持续监听（Ctrl+C 终止）
  - 优雅退出
  - 打印捕获统计

## 3. 测试

- [x] 3.1 测试默认参数运行
- [x] 3.2 测试自定义 IP 和 Port
- [x] 3.3 测试 pcap 模式并用 Wireshark 验证