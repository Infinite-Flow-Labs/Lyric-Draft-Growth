# Source Item x-idoubicc-c974b997f1c8

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/idoubicc/status/2036267766660079765
- Author: idoubicc
- Published At: 2026-03-24T02:24:02Z

## Signals
- Release Signals: 
- Task Hints: 
- Fact Anchors: 17

## Content Preview

Post title: 开源 ClawHost，基于集群的 OpenClaw 多租户部署面板 1. 在 k8s pod 部署 OpenClaw，容器化隔离 2. 挂载 pvc 实现持久存储 3. 支持 Rest API，对 OpenClaw Bot 进行创建、更新、重启等操作，可通过接口管理每个 OpenClaw 内的 models、channels、skills 4. 支持自定义镜像，打包常用的工具、extensions、skills 到 OpenClaw 实例 5. 管理员可创建多个 App，每个 App 可调接口创建多个 OpenClaw Bot 6. 内置管理面板，可视化管理 Apps，Bots 有什么用？ 1. 养虾需求很大，用户需要开箱即用的方案，ClawHost 可以帮你实现 OpenClaw 托管平台 2. 公司内部希望给每个员工配一个专业虾，ClawHost 可以帮你做私有化部署，统一管理 怎么用？ 1. 选择一个云服务厂商，购买托管版 k8s 集群，开通 nas 存储 2. 拉取 ClawHost 项目代码，查看 deploy 文件，通过 kubectl、helm 部署到 k8s 集群 3. 解析一个域名到 k8s 集群，每一个创建的 OpenClaw Bot，可通过子域名访问 Web UI 4. 访问 ClawHost 管理面板，可视化创建 Apps，Bots 5. 如果需要对外提供 SaaS 服务，需要自行实现前端应用，通过 App Token，调用 API 创建 Bot 想玩，不太会玩？ 1. 如果你有用户，有采购 OpenClaw 的需求，可以找我给你创建一批 OpenClaw Bot 2. 如果你有流量，想做 OpenClaw 托管服务，可以找我对接 API，或者我给你搭建 3. 如果你是老板，想跑在公司内网或者自己的云服务器，可以找我给你私有化部署 演示效果可以查看 http://workany.bot，这是基于 ClawHost 实现的 OpenClaw 托管版本 ------ ClawHost 基于 Apache2.0 协议开源，欢迎使用，感谢支持。👇 https://github.com/fastclaw-ai/clawhost

Post summary: 开源 ClawHost，基于集群的 OpenClaw 多租户部署面板 1. 在 k8s pod 部署 OpenClaw，容器化隔离 2. 挂载 pvc 实现持久存储 3. 支持 Rest API，对 OpenClaw Bot 进行创建、更新、重启等操作，可通过接口管理每个 OpenClaw 内的 models、channels、skills 4. 支持自定义镜像，打包常用的工具、extensions、skills 到 OpenClaw 实例 5. 管理员可创建多个 App，每个 App 可调接口创建多个 OpenClaw Bot 6. 内置管理面板，可视化管理 Apps，Bots 有什么用？ 1. 养虾需求很大，用户需要开箱即用的方案，ClawHost 可以帮你实现 OpenClaw 托管平台 2. 公司内部希望给每个员工配一个专业虾，ClawHost 可以帮你做私有化部署，统一管理 怎么用？ 1. 选择一个云服务厂商，购买托管版 k8s 集群，开通 nas 存储 2. 拉取 ClawHost 项目代码，查看 deploy 文件，通过 kubectl、helm 部署到 k8s 集群 3. 解析一个域名到 k8s 集群，每一个创建的 OpenClaw Bo
