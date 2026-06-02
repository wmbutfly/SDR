# SDR 调试工具集

WSL 环境下接收板子 UDP 数据 + 转存 pcap 的工具链。

## 场景

板子 (`192.168.1.1`) 向 PC (`192.168.1.100:8890`) 发送 UDP 报文，载荷为 802.11 Radiotap 帧。

WSL 2 使用 NAT，需 Windows 中转 UDP。

## 文件说明

| 文件 | 运行位置 | 作用 |
|------|---------|------|
| `udp_fwd.py` | **Windows** | 监听 `:8890`，将 UDP 转发到 WSL (`172.21.38.252:8890`) |
| `udp_pcap_saver.py` | **WSL** | 接收 UDP，实时显示 hex+ascii，同时写入 pcap 文件 |
| `test_udp_listener.py` | **WSL** | 仅展示的纯 socket 监听器（无 pcap 保存） |
| `udp_listener.py` | **Ubuntu** | scapy 版监听器，支持 `--iface` 等高级选项（需要 `sudo`） |

## 启动

### 1. Windows UDP 转发

```powershell
python C:\Users\admin\SDR\udp_fwd.py
```

### 2. WSL 监听 + pcap 保存

```bash
nohup python3 /mnt/c/Users/admin/SDR/udp_pcap_saver.py > /tmp/pcap_saver.log 2>&1 &
```

查看实时收包：

```bash
tail -f /tmp/pcap_saver.log
```

输出示例：

```
[#0001] [13:51:50.049] 172.21.32.1:8890 → 331B
         hex: 00003c002f4010a0200800a0200800a0200800a02008000001812b6900000000...
       ascii: ..<./@.. ... ... ... .....+i....
```

### 3. 停止

```bash
pkill -f udp_pcap_saver.py    # WSL
# Windows 转发直接关窗口或 Ctrl+C
```

## pcap 文件

自动生成 `udp_capture.pcap`，用 Wireshark 打开，linktype 选 **802.11 + Radiotap (127)**。

## MQTT 测试

EMQX 运行在 WSL Docker 中：

```bash
docker ps --filter name=emqx
```

端口转发已配置：`192.168.1.100:1883` → WSL `:1883`。

板子测试：

```bash
mosquitto_pub -h 192.168.1.100 -p 1883 -t "board/data" -m "hello"
```

## 部署到真实 Ubuntu

将 `udp_pcap_saver.py` 拷贝到 Ubuntu，直接运行（无需转发层）：

```bash
python3 udp_pcap_saver.py
```

需要 scapy 版则用 `udp_listener.py`：

```bash
sudo apt install python3-scapy
sudo python3 udp_listener.py --ip 192.168.1.100 --port 8890 --mode console
```
