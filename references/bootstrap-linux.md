# Linux 首次配置

仅在目标服务器还没有可复用 Orca runtime 时读取本文件。SSH 是管理入口，安装完成后的 Orca 数据连接可以走 Tailscale。

## 建立前提

1. 确认 CPU 架构、发行版、可用磁盘和目标运行用户。
2. 从 [Orca 官方 Releases](https://github.com/stablyai/orca/releases) 选择匹配架构的软件包，尽量与客户端匹配。根据 [官方安装文档](https://github.com/stablyai/orca/blob/main/docs/site/content/docs/install.mdx) 核实当前安装方法。
3. Ubuntu/Debian 可安装选定的官方 `.deb`，不要在文档中固定一个会过期的文件名。示例中的路径替换为已下载的真实路径：

```bash
sudo apt install /absolute/path/to/orca-ide_VERSION_ARCH.deb
orca-ide --help
orca-ide serve --help
```

4. 两端安装 Tailscale，确认目标主机在同一 tailnet，或已通过共享与访问策略允许访问。若服务器尚未登录，使用当前 [Tailscale 安装说明](https://tailscale.com/docs/install/linux) 完成安装与登录。认证由现有授权流程完成；不把 auth key 放进仓库或提示词。
5. 确认 `tailscaled` 为 active；若任务包含持久运行，再配置它的开机启动。

## 启动一个 runtime

确认目标端口没有已有 orcad 占用后，以目标普通用户运行：

```bash
orca-ide serve --port 6768 --pairing-address <SERVER_TS_IP>
```

`--pairing-address` 只改变向客户端公布的地址，**不控制绑定地址**。检查该版本实际输出和 `ss -lntp`。

- 如果 runtime 仅监听 `127.0.0.1:6768`，继续执行主流程的 TCP 转发步骤。
- 如果 runtime 已在所需 Tailscale 地址监听，不再让 Serve 争抢同一地址/端口。
- 如果 runtime 监听 `0.0.0.0` 或 `::`，核对公网防火墙与现有暴露范围；不能宣称回环隔离已经成立。按版本支持的方式配置监听或限制访问。

首次启动通常在前台运行，终端关闭可能停止服务。先验证再选择该版本支持的 service 模式；不要把临时前台命令描述为开机常驻。

生成的 runtime 配对链接仅交给目标客户端，通过 **Settings → Remote Orca Servers → Add Server** 或当前 CLI `environment add --help` 确认的入口添加。链接含认证材料，不输出到公开日志，不写入本仓库。不要用 mobile-scoped 链接替代 runtime 配对链接。

## 持久运行

先运行 `orca-ide serve service --help`，确认当前版本是否支持服务管理。支持时按其帮助生成/安装服务，核对运行用户、profile、端口与日志。已有受管理部署时保留其生命周期管理，不为它另建冲突的 systemd 服务。

若当前版本不提供 service 子命令，再按实际可执行文件路径和运行用户创建 systemd 服务；若帮助支持 `--supervise`，可让服务管理器使用该模式。不要猜测内部 orcad 的文件名或直接运行来源不明的 Node bundle。

systemd 用户服务需要在注销后继续运行时，核对 user manager 与 linger；不要把仅在当前 SSH 会话有效的环境变量当作持久配置。服务必须使用与首次配对相同的 profile，否则可能生成新的 runtime 身份。

验证服务定义、运行状态与现有 runtime 身份，再报告“配置了开机启动”。没有实际重启测试时注明“重启恢复未实测”。

服务端运行 Codex/Claude 的 CLI、登录态、仓库与依赖都需要在服务端准备；客户端登录不会自动复制过去。按任务需要配置，不在连接修复中扩展到无关安装。
