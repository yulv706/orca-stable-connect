# Orca 1.4.237：保留配对地迁移 SSH 端点

这是历史实施的窄范围兼容方案，仅适用于已核实 schema 的版本。先检查正式 UI/CLI 是否支持迁移；可用时使用正式入口。若当前构建字段不同，停止套用本文件，查看安装构建的 schema 和工具帮助。

## 两份配置共同决定连接方式

macOS 默认 profile 的历史路径如下。自定义 profile、开发构建和其他系统要从实际运行实例发现路径，不能照抄。

```text
~/Library/Application Support/orca/orca-environments.json
~/Library/Application Support/orca/orca-environment-sidecar.json
```

主配置中的 `environments[]` 保存环境、端点和认证字段。sidecar 中的 `entries[ENV_ID].orcadDeployment` 保存 SSH 部署关联。只改端点可能留下 SSH 依赖；把 sidecar 字段移到主配置也不正确，旧构建会剥离未知字段。

本次历史 schema 中：

```typescript
connectionDependency: z.literal('ssh-tunnel').optional()
```

因此，解除 SSH 依赖要**删除 `connectionDependency` 键**。不能写成 `null`、`"direct"` 或空字符串。历史上写成 `null` 后出现 `Skipping 1 unreadable server record(s)`，目标环境暂时从列表消失；恢复备份后才修复。

## 执行前建立恢复点

1. 确认新地址的 WebSocket 探针已通过，原管理入口仍可用。
2. 记录目标 `ENV_ID`、`runtimeId`、首选 endpoint ID 和环境列表；输出中去掉认证材料。
3. 识别配置的写入者。优先关闭本地客户端以避免覆盖编辑；先检查本机是否也承担其他共享 runtime，不能为了改客户端配置影响其他服务。关闭客户端不等于关闭远端 orcad。
4. 将两份配置完整备份到用户私有目录，权限目录 `0700`、文件 `0600`，不要放入 Git 仓库。缺少任一预期文件或 JSON 无法解析时先停止。
5. 验证目标环境只匹配一条，`preferredEndpointId` 只匹配该环境的一条端点；确认 sidecar 的 binding 与同一配对修订和首选端点一致。

不要通过打印整份 JSON 来检查字段。完整配置含 `deviceToken` 等凭据；备份也应按凭据保管。

## 最小变更

以发现出的对象为准，下列是操作语义，不是可原样执行的全文件模板：

```python
# target: 按 ENV_ID 唯一找到的 environment
# preferred: 按 target['preferredEndpointId'] 唯一找到的 endpoint
preferred['endpoint'] = 'ws://<SERVER_TS_IP>:6768'
target.pop('connectionDependency', None)
sidecar['entries'][ENV_ID].pop('orcadDeployment', None)
```

必要时更新该版本要求的 `updatedAt`。保留所有其他记录及字段，尤其是：

- `id`、`runtimeId`、`pairedDeviceId`、`pairingRevision`。
- endpoint 的 `id`、`deviceToken`、`publicKeyB64`。
- `preferredEndpointId` 与 sidecar 的 `binding`。
- 其他环境的全部数据。

不要盲目改 `endpoints[0]`，它不一定是首选端点。不要随意删除整个 sidecar entry。

若出现 `sshAccess`、`pendingSshAccessOperation`、WSL 部署或其他新型关联，本次案例没有覆盖；使用当前构建的正式迁移/解除关联逻辑，不按以上三行推断。

写入前重新比较文件内容与读取时是否一致；不一致就重新读取和决策。使用同目录临时文件与替换操作避免单文件截断，并保留 `0600`。两份文件不能组成跨文件原子事务，因此需要停止写入者、完整备份，以及任一失败时同时恢复两份文件。

## 验收和恢复

重新打开客户端，运行：

```bash
orca environment list --json
orca environment show --environment <ENV_ID> --json
orca status --environment <ENV_ID> --json
orca repo list --environment <ENV_ID> --json
```

确认环境记录未消失、目标端点已变更、SSH 依赖字段已不存在，并且原 runtime ID 的认证 RPC 成功。主流程中的即时连接与持续连接验收分别执行。

出现 schema 警告、环境消失、认证失败或原配置被覆盖时，停止继续改字段。关闭配置写入者，**同时恢复主配置和 sidecar**，验证权限与 JSON，再用原连接路径检查环境。不要通过重新配对、删环境或重启远端 agent 来掩盖迁移失败。

本案例最终完成了即时认证连接，后续“重启 Orca 弹出提醒”的请求被中断，没有记录完成结果。不要把这份参考当作已覆盖客户端重启提示的证明。
