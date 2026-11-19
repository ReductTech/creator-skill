# 术库本地预览

Creator Skill 内置 Shuku 的播放器、播放入口和课程运行时。可从课程目录查看制作中的页面、翻页、讲稿和全屏放映。安装本仓库的 Node 依赖后即可本地使用。

## 快速开始

需要 **Node.js 24+**（含 npm）。在 Creator Skill 根目录执行：

```powershell
npm run setup
npm start -- --demo
```

打开终端显示的本地地址，在列表中播放入门课件。默认从 5174 开始寻找可用端口。要指定固定端口，可加上 `--port 5175`。终端保持运行，按 `Ctrl+C` 停止。

先看播放器本身，可打开 [交互演示](http://127.0.0.1:5174/?demo=1)，体验按钮、方向键、大纲与全屏，不需要后端服务。

问卷与调研的界面效果可打开 [问卷演示](http://127.0.0.1:5174/?demo=survey)，包含图片投票、综合问卷、表格量表与管理者统计。使用本地示例数据，刷新后恢复初始状态，不连接数据库，也不模拟真实登录或线上提交。

[标准问卷控件预览](http://127.0.0.1:5174/?demo=survey-template) 使用随仓库提供的 Shuku 标准模板。实现入口在 `preview/survey-template-demo.tsx`。智能体接入与可复制源码见[问卷参考](../references/design/surveys.md)。

修改源码时预览会热更新。拉取了依赖更新后，在仓库根目录重新运行 `npm run setup`。

## 查看自己的课件

在 Creator Skill 根目录运行：

```bash
npm run new -- ../my-course
npm start -- --project ../my-course
```

新工程会获得课件和页面的新 UUID、默认 Shared 和 `target-root.json`。已有工程可以用 `npm start -- --context "<配置文件绝对路径>"`，直接复用创作工具的窗口配置。配置示例：

```json
{
  "targetRoot": "D:/Courses/MyProject"
}
```

路径必须是已存在的课程工程绝对路径。支持 `modules/<课程UUID>/outlines.json` 和平铺 `<课程UUID>/outlines.json` 两种布局。课件源码与素材保留在目标工程，不搬进播放器目录；风格从目标的 `shared/` 或 `modules/shared/` 读取，工程缺少风格时使用内置的 Shuku 默认风格。

预览默认使用内置的 Shuku 课程运行时。需要联调另一份 Shuku 源码时，将本目录 `.env.example` 复制为 `.env.local`，填写以下可选配置。

```dotenv
SHUKU_ROOT=D:/Projects/Shuku
```

指定 `--standalone` 可强制使用仓库内置的运行时。AI 评阅、模型、GPU 和在线问卷提交需要对应平台服务。

保存配置后重启预览，从课程列表选择“播放课件”或“课程导览”。只有大纲、没有实现入口的课程不能播放。深链接格式为：

```text
http://127.0.0.1:5174/?course=<课程UUID>&view=ppt&page=<页面UUID>
http://127.0.0.1:5174/?course=<课程UUID>&view=guide
```

`page` 可省略，不使用旧 `slide` 参数。Guide 使用与 TSX 文件名同名的命名导出，PPT 入口导出 `deck`，与当前 Shuku 保持一致。

## 发布到术库

课程预览顶部保留「全屏放映」「发布到术库」。左侧大纲和底部讲稿可继续使用。点击发布后，Creator Skill 用现有 `course.pack` 打包当前课程，并在浏览器打开术库创作页。支持交接的术库创作页会在登录后带入 ZIP，作者在预审页确认上传，随后按术库的构建、审核和发布流程处理。也可在预览弹窗下载 ZIP。

本地对接测试可在 `.env.local` 设置 `CREATOR_SKILL_SHUKU_ORIGIN`。默认地址是 `https://shuku.reduct.cn`。

## 检查与构建

```powershell
npm run typecheck
npm run build
```

类型检查覆盖播放器与预览入口；播放器库构建结果为 `dist/index.js`、类型声明和 `dist/style.css`。这不是课程发布包，也不是可直接部署的课程网站；课程源码 ZIP 通过 [course.pack](../references/engineering/delivery.md) 交付。

提交时保留 `src/`、`preview/`、`scripts/`、配置、`.env.example` 和 `package-lock.json`。已忽略 `node_modules/`、`dist/`、`.npm-cache/`、Vite/TypeScript 缓存、日志和本地环境文件。已有本地构建可以保留，Git 不会将它们纳入新提交。

## 常见问题

- **列表为空**：检查目标路径、课程 UUID 目录与 `outlines.json`；新增课程目录或修改配置后重启预览。
- **显式配置的 Shuku 运行时不存在**：检查 `SHUKU_ROOT` 下的 `packages/course-runtime/`，或使用 `--standalone` 选择内置运行时。
- **素材加载失败**：素材放在课程 `assets/`，通过单参数 `moduleAssetUrl('真实相对路径')` 读取。
- **模型、评阅、训练不可用**：这些功能通过术库宿主 RPC 调用服务，要在 Shuku 学习页面验证；本地预览不模拟登录、GPU 或云端返回。
- **预览正常是否代表官网可用**：还须执行平台校验、真实构建及最终产物验收，本地源码预览不能代替官网验收。

`src/`、`runtime/course-runtime/` 和 `runtime/default-style/` 分别来自 Shuku 的 `packages/player/src/`、`packages/course-runtime/` 和 `packages/course-styles/default/`。播放入口来自 `tooling/course-build/runtime/`。这些源码基于 Shuku 提交 `91c580279871860482bf0137d14ecf9e46747520`。Creator Skill 在播放器中挂接精简操作栏，并由 `preview/` 和 Vite 配置提供课程发现、深链接、源码热更新和发布交接。
