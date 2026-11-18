# 论文图网页预览

本目录提供论文图的网页 PPT、前后翻页和多页导览。图组源码保存在 `modules/`，通过现有页面入口加载。

本文命令均在 `creator-paper/` 根目录执行，路径相对于仓库根目录。

## 环境要求

从 [Node.js 官方下载页](https://nodejs.org/en/download) 安装 Node.js 24 或更高版本，安装包包含 npm。

```sh
node --version
npm --version
```

## 安装与启动

首次使用且尚未安装依赖时：

```sh
npm --prefix player-preview ci
```

启动预览：

```sh
npm --prefix player-preview run dev -- --host 127.0.0.1 --port 5176 --strictPort
```

打开 [预览首页](http://127.0.0.1:5176/)。保持终端运行，按 `Ctrl+C` 停止。若服务已经运行，直接打开页面即可。

命令适用于 Windows、macOS 和 Linux。PowerShell 若限制 `npm.ps1`，用 `npm.cmd` 替换命令中的 `npm`。由 AI 助手安装依赖时，遵循已保存的安装偏好。

## 打开图组

```text
http://127.0.0.1:5176/?course=<图组UUID>&view=ppt&page=<页面UUID>
http://127.0.0.1:5176/?course=<图组UUID>&view=guide
```

`course` 是现有播放器的图组参数，`page` 对应 `outlines.json` 中的单页 UUID。`view=ppt` 按页查看，`view=guide` 纵向查看整套图。

图组应位于 `modules/<图组UUID>/`，包含 `outlines.json`、PPT 入口、Guide 入口及对应页面实现。修改已有图保留 UUID，新增页面再分配新的 UUID。

## 配置与检查

启动命令使用项目已有预览配置。机器相关设置放在 `player-preview/.env.local` 等本地配置中；迁移项目时检查配置，不在公共文档中写入固定机器目录。

- 列表为空：检查图组是否位于 `modules/`，`outlines.json` 与页面入口是否完整。
- 配置缺失：按终端提示补齐项目配置，再重新启动。
- 素材加载失败：检查图组 `assets/` 和 `moduleAssetUrl` 的相对素材路径。
- 端口占用：优先使用已有预览；确需新服务时，将启动命令中的 `--port 5176` 换为可用端口，并返回实际地址。
- 页面修改：开发服务会热更新，实际核对字号、连线、边界与素材显示。

按任务需要执行播放器检查：

```sh
npm --prefix player-preview run typecheck
npm --prefix player-preview run build
```

`build` 构建播放器库，不是把单张论文图导出为 PDF。论文图应从当前网页按实际比例导出。

依赖、缓存和构建产物不纳入正式论文图素材。主要绘图流程见根目录的 [README](../README.md) 和 [SKILL.md](../SKILL.md)。
