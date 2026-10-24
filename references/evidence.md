# 来源与验证边界

本 Skill 根据用户指定的历史会话整理。历史链接仅供同一 Codex 环境回溯，其他 agent 不需要访问历史即可执行主流程：

- `codex://threads/01a16748-d8a7-7472-bc40-b04ec538cdc7`
- 历史会话标题：下载服务器上的两个修改文件。
- 本 Skill 取材于其后半段的连接诊断与迁移，发生于 2026-10-23。

## 历史实际确认的结果

1. 原连接使用客户端回环 WebSocket 端点和 SSH 隧道；Tailscale 路径在测试中经过 DERP，延迟和限时下载表现较差。
2. 用户在云安全组增加 UDP 41641 规则后，`tailscale ping` 显示公网端点直连，一次响应为 68 ms。
3. 对照服务器上的 Orca 同样监听回环。它的 Tailscale 地址监听由 `tailscaled` 提供；`tailscale serve status` 显示 TCP 转发。早期“Orca 本身直接监听 Tailscale”的说法被后续检查修正。
4. 在目标服务器建立 `tailscale serve --bg --tcp 6768 tcp://127.0.0.1:6768` 后，原 orcad 保持运行。首次无权限执行被拒绝；历史通过配置 operator 后重试成功。本 Skill 默认采用单次 sudo，避免不必要的长期授权。
5. 客户端向新地址发起 WebSocket 升级，返回 HTTP 101；一次测得升级往返约 70 ms。这不是认证成功的证据。
6. 客户端初次把 `connectionDependency` 写成 `null` 后，目标记录被 schema 拒绝；恢复备份后，改为删除键、更新原首选端点并清除 sidecar 的 `orcadDeployment`。
7. 最后使用已保存环境执行 `orca status --environment ... --json`，得到原 runtime 的 `reachable: true`、`connectionState: connected`。历史输出中的 Orca 版本为 1.4.237，服务端已有 agent 未被重启。

上面的响应时间是单次历史观测，不是服务指标或未来承诺。原始地址、环境 UUID、密码、配对密钥和完整日志没有随 Skill 分发。

## 2026-10-24 的核对

- 本地安装的 Orca 为 1.4.237，Tailscale 为 1.104.2。
- 本机 CLI `serve --help` 确认 `--pairing-address` 仅更改公布地址，固定 `--port` 可避免自动换端口。
- 本机 `environment list` 仍显示两个保存的 Tailscale WebSocket 端点。
- 使用本仓库的探针重新访问目标服务器，收到有效 HTTP 101；随后通过原已保存环境执行 Orca 状态 RPC，得到 `state: ready`、`reachable: true`、`connectionState: connected`、版本 1.4.237。本轮没有修改线上配置或重启进程。
- 探针的 8 个本地服务模拟测试通过，覆盖有效升级、分段响应、错误的升级校验值、普通 HTTP、超时、超长响应头、TCP 拒绝和非法主机输入。Skill frontmatter 与本地文档链接已检查。
- 参考本地 Orca 源码提交 `e208c4712a76c1fbee7a72fbddc29fb85f283afb` 的远程服务文档与 schema；源码 checkout 不保证等于所有安装构建，实际操作仍以运行构建为准。

## 官方参考

- [Tailscale TCP forwarder 与 Serve 命令](https://tailscale.com/docs/reference/tailscale-cli/serve)：核对 TCP 转发语法、`--bg` 与持久化行为。
- [Tailscale 防火墙端口](https://tailscale.com/docs/reference/faq/firewall-ports)：默认 UDP 41641 可改；放行监听端口有助于直连，不能保证所有 NAT 条件下成功。
- [Orca 官方仓库](https://github.com/stablyai/orca) 与 [Releases](https://github.com/stablyai/orca/releases)：核实软件来源。
- [Orca 远程服务器文档](https://github.com/stablyai/orca/blob/e208c4712a76c1fbee7a72fbddc29fb85f283afb/docs/site/content/docs/remote-servers.mdx)：区分远程 runtime、客户端与 agent 所在主机。
- [Orca runtime 配置 schema](https://github.com/stablyai/orca/blob/e208c4712a76c1fbee7a72fbddc29fb85f283afb/src/shared/runtime-environments.ts)：说明主配置与扩展状态分离，以及旧字段的 optional 约束。

## 我们可能错了

这次迁移只有当时的连接与认证结果，没有长期掉线率、跨网络持续压测或服务端重启恢复实验。历史最后的“重启 Orca 后弹出提醒”请求被中断，没有解决记录。因此“此方案保证重启后始终稳定”没有证据支持。

其他 Orca 版本可能已有正式迁移入口，可能改变 schema、监听方式或升级鉴权。若版本帮助、运行状态或源码显示不同，应调整对应分支，不继续套用 1.4.237 的离线编辑方式。
