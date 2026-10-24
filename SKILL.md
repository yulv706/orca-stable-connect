---
name: orca-stable-connect
description: Configure or troubleshoot stable remote Orca connections over Tailscale, including DERP diagnosis, tailnet TCP forwarding, and migration from an SSH tunnel while preserving pairing and running agent sessions. Use for Orca remote connection setup or repeated disconnects.
---

# Orca 稳定连接

让客户端通过 Tailscale 访问现有远程 Orca，保留配对和服务端正在运行的 agent。默认目标拓扑如下；实际端口以探测结果为准。

```text
客户端 Orca
  └─ ws://<SERVER_TS_IP>:6768
       └─ Tailscale 加密网络（优先验证 UDP 直连）
            └─ 服务端 tailscaled / tailscale serve
                 └─ tcp://127.0.0.1:6768
                      └─ 已有 orcad 与 agent 会话
```

区分两件事：Tailscale 的 direct/relay 是底层网络路径；Orca 是否依赖 SSH 隧道是应用连接方式。完成其中一项，不代表另一项也完成。`tailscale serve` 可以经 DERP 工作，但不保证改善受限中继的延迟和吞吐。

## 收集输入并选择工具

从当前配置发现以下输入，缺少且无法发现时才询问：

- 客户端与服务端的操作系统、Orca/Tailscale 版本。
- `SERVER_TS_IP`：服务端的 Tailscale 地址；确认它属于目标服务器。
- `ORCA_PORT`：现有 orcad 的实际回环监听端口，常见为 `6768`。
- `ENV_ID`：客户端现有环境的完整 ID；不要只按模糊名称匹配。
- 服务端已有登录入口、现有会话及服务启动方式。

优先使用当前环境的 Orca CLI。先按 `ORCA_CLI_COMMAND`、开发会话的 `orca-dev`、Linux 外部终端的 `orca-ide`、其他环境的 `orca` 选择一次，后续保持同一入口。Linux 外部终端的 `/usr/bin/orca` 可能是屏幕阅读器。

运行所选入口的 `skills get orca-cli --json` 读取版本匹配指南。未支持的参数用该版本 `--help` 核实。所选入口失败时报告确切错误，不静默换另一个构建。

下文的 `orca` 是 macOS 客户端示例。服务端命令在目标 Linux 机器执行。Mac 上找不到 `tailscale` 时，可使用 `/Applications/Tailscale.app/Contents/MacOS/Tailscale`。

## 1. 只读确认当前状态

在客户端执行：

```bash
orca environment list --json
tailscale status
tailscale netcheck
tailscale ping -c 8 <SERVER_TS_IP>
```

环境端点为 `ws://127.0.0.1:<LOCAL_PORT>` 时，查看是否存在 `connectionDependency: "ssh-tunnel"` 及部署信息；不要仅凭回环地址判断来源。Tailscale 初次 ping 可能先经中继，再转为直连；检查后续响应和 `tailscale status` 的 direct/relay。

通过已有管理入口，在服务端执行：

```bash
tailscale version
tailscale ip -4
tailscale serve status
ss -lntp
sudo -n ss -lunp
systemctl is-active tailscaled
systemctl is-enabled tailscaled
```

`sudo -n` 失败表示当前不能免交互提权，不代表端口没有监听。仅检查相关端口，避免把原始配置、配对链接或进程中的凭据输出到报告。

若服务端没有 Orca，先读 [references/bootstrap-linux.md](references/bootstrap-linux.md)。已有运行实例时复用它，不安装第二套或启动第二个 serve。

## 2. 改善 Tailscale 路径

若已 direct，跳到下一步。若持续 relay/DERP：

1. 检查两端 `tailscale netcheck` 的 UDP 结果。
2. 查明服务端 tailscaled 的实际 UDP 监听端口。默认常见为 `41641`，不能只凭默认值开规则。
3. 对照云安全组、主机防火墙和 NAT。只有任务已授权网络配置变更时，才补齐必要规则；否则给出已核实的规则要求。
4. 在云服务器入站放行实际 UDP 端口；来源范围按客户端网络与既有访问策略确定。客户端公网出口会变化时，说明固定来源的限制。主机防火墙仅在实际阻断时调整。
5. 保持 Tailscale 所需出站通路，重新运行 `tailscale ping` 与 `tailscale status`。

只为 Tailscale 放行 UDP 端口，**不要把 Orca 的 TCP 6768 暴露到公网**。放行 UDP 后仍不 direct 时继续排查客户端 Wi-Fi/NAT/UDP；不要重启生产会话试运气。详见 [references/troubleshooting.md](references/troubleshooting.md)。

## 3. 在 tailnet 内转发现有回环端口

前提：已确认服务端 `127.0.0.1:<ORCA_PORT>` 属于目标 orcad，并记录当前 Serve 配置。若 tailnet 同端口已被其他服务占用，先解决冲突，不能覆盖。

服务端执行，以下示例端口为 `6768`：

```bash
sudo tailscale serve --bg --tcp 6768 tcp://127.0.0.1:6768
tailscale serve status
sudo ss -lntp
```

应看到 tailnet 地址的 `6768` 转发到 `127.0.0.1:6768`。外侧监听通常属于 `tailscaled`，内侧仍属于原有 orcad。无须重启 orcad、Claude、Codex 或 tailscaled。

`Access denied: serve config denied` 时使用已授权的 sudo 执行该条命令。历史会话通过设置 `--operator` 解决过权限问题，但 operator 会授予该用户更多 Tailscale 管理能力，不作为默认步骤。

使用 TCP forwarder，避免误配成默认 HTTPS 站点；不启用 Funnel。`--bg` 使转发独立于 SSH 会话，并可在系统重启后恢复；这不等于 orcad 本身已有开机启动。

## 4. 从客户端验证转发

在客户端执行本 skill 的只读探针：

```bash
python3 scripts/probe_websocket.py --host <SERVER_TS_IP> --port 6768
```

`websocket_upgrade: true` 只证明 TCP 与 WebSocket 升级可达。它**没有进行 Orca 配对、认证或加密会话握手**。不能据此宣称 Orca 已连接。

探针失败则先修复网络/Serve/服务端监听，保留原 SSH 连接。

## 5. 切换客户端，保留现有配对

先查看安装版本是否提供正式的地址编辑或连接迁移功能；优先使用该入口。目标端点为 `ws://<SERVER_TS_IP>:<ORCA_PORT>`。

- 保留 environment ID、runtime ID、配对修订、设备身份及现有认证字段。
- 不使用 `environment rm`、`stop`、`forget` 或重新部署来代替地址迁移。
- 不在日志、Git 或回复中复制 `deviceToken`、私钥、配对 URL。

Orca 1.4.237 的历史迁移涉及主配置与 sidecar 两个文件。只有正式入口不可用且已核实本机 schema 相符时，读 [references/migration-1.4.237.md](references/migration-1.4.237.md) 再操作；不能把旧字段编辑方式直接套到新版本。

## 6. 验收并报告边界

客户端使用已保存的环境执行：

```bash
orca environment show --environment <ENV_ID> --json
orca status --environment <ENV_ID> --json
orca repo list --environment <ENV_ID> --json
```

逐项核实：

- 保存的首选端点确实为目标 Tailscale 地址，已解除对本机 SSH 隧道的依赖。
- 远端 `status` 显示运行时可达、`connectionState: connected`，runtime ID 与迁移前一致。
- `repo list` 等实际只读 RPC 成功；没有新建或重复启动 agent。
- 原服务端会话仍在。需要检查终端时先列举，不发送测试文字或中断输入。
- 多次连接检查未见掉线；若只做了瞬时检查，明确写“即时连接通过，长期稳定性未验证”。

`app.running: false` 或 `desktopWindowStatus: blocked` 可以是正常的 headless 状态；以 runtime 可达性判断连接。

分别报告 Tailscale direct/relay、WebSocket 可达性、Orca 认证/RPC、持久化启动情况。客户端重开与服务端重启是不同验收项。没有维护窗口时不为验收强制重启；报告未验证项和配置备份位置。

## 回滚

客户端切换失败时恢复原客户端配置与原连接路径，按迁移参考核对两份文件。若本次新增了 Serve，且客户端已退回原路径，再仅撤销这个端口：

```bash
sudo tailscale serve --tcp=6768 off
```

若此前该端口已有 Serve，恢复它原来的映射。不执行 `tailscale serve reset`，它会影响其他转发；不为了回滚网络配置停止 orcad 或 agent。

## 依据

最终实施结果和先前误判的区别见 [references/evidence.md](references/evidence.md)。该案例验证的是一次迁移，不能承诺所有 NAT、版本或重启场景都稳定。
