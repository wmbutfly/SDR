# UDP Pcap Saver

UDP 监听 + 实时展示 + pcap 归档。纯 socket，无需 scapy。

## 文件说明

| 文件 | 运行位置 | 作用 |
|------|---------|------|
| `udp_pcap_saver.py` | **WSL / Ubuntu** | UDP 监听，hex/ascii 实时显示，pcap 文件保存 |
| `udp_fwd.py` | **Windows** | 将 UDP 从 Windows 转发到 WSL（WSL2 NAT 需要） |
| `udp_listener.py` | Ubuntu | scapy 版（需要 `sudo`），功能更全 |

## 快速开始

```bash
python3 udp_pcap_saver.py
```

自动生成 `wifi_20260602_141008.pcap`，监听 `0.0.0.0:8890`。

## 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--ip` | `0.0.0.0` | 监听 IP |
| `--port` | `8890` | 监听端口 |
| `-t`, `--type` | `wifi` | 数据类型：`wifi`, `bt`, `bt_phdr` |
| `-o`, `--output` | 当前目录 | 输出目录，不存在自动创建 |
| `-s`, `--max-size` | `1M` | 单文件上限，超限自动滚动 |
| `-m`, `--max-total` | `1G` | 总磁盘占用上限，超限删最老 |
| `-n`, `--max-files` | `0` | 总文件数上限，超限删最老（0=不限） |
| `-c`, `--channel` | `1` | WiFi 信道号，仅 wifi 有效 |
| `--linktype` | 自动 | 强制指定 pcap linktype，覆盖 `--type` |
| `--mqtt-host` | `localhost` | MQTT broker 地址 |
| `--mqtt-port` | `1883` | MQTT broker 端口 |
| `--mqtt-topic` | `FromSDR` | MQTT 主题 |
| `--mqtt-user` | `admin` | MQTT 用户名 |
| `--mqtt-password` | `123456` | MQTT 密码 |
| `--mqtt-qos` | `1` | MQTT QoS 级别（0/1/2） |

## 类型

| `--type` | 文件名 | linktype | 说明 |
|----------|--------|----------|------|
| `wifi` | `wifi_20260602_141008.pcap` | 127 | 802.11 + Radiotap |
| `bt` | `bt_20260602_141008.pcap` | 251 | Bluetooth LE LL |
| `bt_phdr` | `bt_phdr_20260602_141008.pcap` | 256 | Bluetooth LE LL + PHDR |

## MQTT 通知

启动时发送 MQTT 通知：

- **wifi**: `{"op": "start", "mod": "wifi", "channel": "1"}`
- **bt/bt_phdr**: `{"op": "start", "mod": "bt"}`（无 channel）

停止时统一发送 `{"op": "stop"}`。

消息为 **QoS 1 + 保留(retain)**，确保至少送达一次，新订阅者立即拿到当前状态。不限制订阅者数量。

```bash
# 订阅端无需特殊参数，正常 sub 即可（第一条就是保留消息）
mosquitto_sub -h localhost -p 1883 -t FromSDR -u admin -P 123456

# 或 MQTTX 直接 subscribe FromSDR
```

EMQX broker 运行在 Docker：

```bash
# 新机器一键安装
sudo ./setup_emqx.sh

# 或单独启动
docker run -d --name emqx --restart always \
  -p 1883:1883 -p 18083:18083 \
  -v emqx-data:/opt/emqx/data \
  emqx/emqx:latest
```

Dashboard: `http://localhost:18083` 账号 `admin` 密码 `public`。
连接需用户认证，创建方式见源码或使用匿名模式。

## BT 接收

用法与 WiFi 相同，改 `-t` 即可。pcap 文件 linktype=251/256，Wireshark 自动按 BLE 解析。

```bash
python3 udp_pcap_saver.py -t bt -o /data/bt_captures/ -s 10M -m 200M
```

## WSL2 转发

WSL2 使用 NAT，需 Windows 中转才能收到板子的 UDP。

**Windows 上跑：**

```powershell
python C:\Users\admin\SDR\udp_fwd.py
```

**WSL 里跑：**

```bash
nohup python3 udp_pcap_saver.py > /tmp/pcap_saver.log 2>&1 &
tail -f /tmp/pcap_saver.log
```

**停止：**

```bash
kill $(cat /tmp/pcap_saver.pid)
```

## 输出示例

```
[#0001] [15:26:28.294] 127.0.0.1:9020 → 100B
         hex: e96cb1036ecb7e73ed304bfbda7789435b613d5cb4fe03d12f2e2ab4e28d2b6a...
       ascii: .l..n.~s.0K..w.C[a=\..../.*...+j
```

## 滚动文件命名

自动命名时每次滚动生成独立文件：

```
wifi_20260602_141008.pcap          ← 初始
wifi_20260602_141008_001.pcap      ← 第一次滚动
wifi_20260602_141008_002.pcap      ← 第二次滚动
```

超过 `-n` 或 `-m` 限制时，最老文件自动删除。

## 部署到真实 Ubuntu

直接跑，不需要转发层：

```bash
python3 udp_pcap_saver.py --port 8890 -t wifi -s 50M -m 500M
```
