# Orca Stable Connect Skill

给 agent 使用的 Orca 远程连接配置与排错 Skill。入口是 [SKILL.md](SKILL.md)。

适用场景：Orca 经 SSH 隧道频繁掉线、Tailscale 长期走 DERP、迁移到 tailnet 地址时需要保留已有配对和运行中的 agent。

默认方案为 `Orca 客户端 → Tailscale → tailscale serve TCP 转发 → 已有回环 orcad`。把网络路径、端口可达性和 Orca 认证分别验收。

## 安装

把本仓库克隆到 agent 的 skill 目录，或让 agent 直接读取仓库中的 `SKILL.md`。Codex 示例：

```bash
git clone https://github.com/yulv706/orca-stable-connect.git \
  ~/.codex/skills/orca-stable-connect
```

私有仓库需要先配置 GitHub 读取权限。其他 agent 使用其自己的 skill 发现目录；不要假定所有工具都读取 `~/.codex/skills`。

## 调用

```text
使用 $orca-stable-connect 检查这台服务器的 Orca 断线问题。
先发现现有环境和 Tailscale 路径；迁移时保留配对和运行中的 agent。
```

主流程会按情况引导读取 Linux 首次安装、旧版配置迁移与故障处理参考。只读 WebSocket 探针使用 Python 3 标准库，不依赖第三方包，也不接收配对凭据：

```bash
python3 scripts/probe_websocket.py --host <SERVER_TS_IP> --port 6768
python3 -m unittest discover -s tests -v
```

## 适用范围

历史实施日期为 2026-10-23，Orca 版本为 1.4.237；2026-10-24 核对了客户端版本与本机 CLI。旧版文件编辑方案按版本单独隔离。所有地址均为占位示例；仓库不包含原始会话、服务器地址、密码、token 或配对链接。

依据与未验证事项见 [references/evidence.md](references/evidence.md)。
