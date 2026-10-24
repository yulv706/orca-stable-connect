# 按证据分层排错

## Tailscale 在线，但一直 relay/DERP

`tailscale status` 中 `online` 或能 ping 通，只能证明可达。连续 `tailscale ping` 后仍显示 DERP 时，对照两端 `netcheck`、服务端实际 UDP 监听、云安全组、主机防火墙与客户端网络限制。

云安全组和主机防火墙是两层。`ufw inactive` 不等于云侧已放行。历史案例在云安全组放行 UDP 41641 后变为 direct；这支持该案例的修复判断，不意味着所有 DERP 都由同一原因导致。UDP 规则也不能用 TCP `nc` 测试来证明。

Wi-Fi 切换可能改变 NAT、出口和代理。分别记录测试网络、路径与时间。系统 HTTP/SOCKS 代理不自动保证改善 Tailscale 的 UDP 路径；临时代理或 exit node 也不能当作已验证的修复。

## Serve 提示 Access denied

若有授权的 sudo 权限，针对该次命令使用 `sudo tailscale serve ...`。不要默认设置 `tailscale set --operator=$USER`；后者改变长期管理权限。没有权限时报告所需命令与确切错误。

## 已 direct，但 TCP/WebSocket 失败

先在服务器检查回环 orcad 是否存在，Serve 是否指向它的实际端口，再检查 tailnet 的访问策略和目标 IP。`tailscale ping` 成功不证明 TCP 6768 允许通过。

- Connection refused：核查监听和端口、服务状态。
- Timeout：核查目标地址、路由、访问策略和防火墙。
- HTTP 200/404：可能连到了 HTTP 服务；核查 Serve 模式与目标进程。
- HTTP 401/403：记录版本与响应，可能有前置认证或策略；不要因此关闭认证。
- HTTP 101 且升级头正确：网络升级通过，继续做 Orca 认证 RPC。

在部分版本/部署中，运行时可能拒绝无配对的升级请求；探针失败不能单独证明 Orca 不可用。用现有已配对环境的真实 RPC 交叉判断。

## WebSocket 探针通过，但 Orca 不连接

核查客户端仍在用本机隧道地址、首选端点错误、SSH 部署依赖残留、runtime 身份不匹配、授权已撤销或版本不兼容。不要重新生成凭据来试错；先保留现有配对并比较身份。

## 环境从列表消失

先查 CLI 的 `Skipping ... unreadable server record(s)` 等警告。1.4.237 曾因 `connectionDependency: null` 拒绝读取记录。读取对应版本的迁移参考，恢复主配置和 sidecar 后再修复，不能把“列表中看不到”解释为服务器被删除。

## 重开客户端后又回到 SSH，或出现提醒

核查磁盘是否被旧客户端覆盖、主配置与 sidecar 是否匹配、是否编辑了错误 profile，以及当前运行构建是否支持那些字段。读取真实提示文本与日志再决定；历史会话的最后一个重启提醒未处理完，没有可复用的确定修复。

## SSH 退出或服务器重启后掉线

分别检查 `tailscale serve --bg` 是否仍存在、tailscaled 是否启动、orcad 是否由持久服务管理，以及服务是否读取原 profile。Serve 的持久化只保护转发配置，不会替 orcad 设置开机启动。没有维护窗口时检查服务定义，不强制重启活跃服务器。

## 避免把测试本身变成负载

先用小量 ping、WebSocket 升级和只读 RPC；带宽确实是待排查项时再做限量、限时测试。不要用无限流、反复新建 agent 或关闭现有终端来证明连接。
