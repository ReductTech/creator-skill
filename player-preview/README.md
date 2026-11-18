# Player Preview：本地播放器与课件预览

可选开发者入口；course.pack会在依赖齐全时自动执行本地构建与浏览器检查；缺依赖遵循已保存安装意愿。查看制作中的课件、翻页和讲稿，也可单独开发播放器。仓库保留源码、配置与锁文件；依赖、缓存和构建结果由使用者在本机生成，不提交 Git。

## 快速开始

需要 **Node.js 24+**（含 npm）。在 Creator Skill 根目录执行：

```powershell
npm run setup
npm start -- --demo
```

打开终端显示的本地地址，在列表中播放入门课件。默认从 5174 开始寻找可用端口。要指定固定端口，可加上 `--port 5175`。终端保持运行，按 `Ctrl+C` 停止。

先看播放器本身，可打开 [交互演示](http://127.0.0.1:5174/?demo=1)，体验按钮、方向键、大纲与全屏，不需要后端服务。

问卷与调研的界面效果可打开 [问卷演示](http://127.0.0.1:5174/?demo=survey)，包含图片投票、综合问卷、表格量表与管理者统计。使用本地示例数据，刷新后恢复初始状态，不连接数据库，也不模拟真实登录或线上提交。

[标准问卷控件预览](http://127.0.0.1:5174/?demo=survey-template) 使用 Shuku 源码里的标准模板。实现入口在 `preview/survey-template-demo.tsx`。智能体接入与可复制源码见[问卷参考](../references/design/surveys.md)。

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

路径必须是已存在的课程工程绝对路径。支持 `modules/<课程UUID>/outlines.json` 和平铺 `<课程UUID>/outlines.json` 两种布局。课件源码与素材保留在目标工程，不搬进播放器目录；默认风格从目标的 `modules/shared/` 或 `shared/` 读取，目标缺少时使用本仓库附带的默认 `shared/`。

独立运行时支持课件播放、讲稿、本地状态及课件素材。需要使用原生 Shuku 运行时时，预览会查找与 Creator Skill 同级的 `Shuku/`。位置不同时，将本目录 `.env.example` 复制为 `.env.local`，填写：

```dotenv
SHUKU_ROOT=D:/Projects/Shuku
```

有本地 Shuku 源码时也可以用 `--standalone` 强制使用内置运行时。AI 评阅、模型、GPU 和在线问卷提交需要对应平台服务。

保存配置后重启预览，从课程列表选择“播放课件”或“课程导览”。只有大纲、没有实现入口的课程不能播放。深链接格式为：

```text
http://127.0.0.1:5174/?course=<课程UUID>&view=ppt&page=<页面UUID>
http://127.0.0.1:5174/?course=<课程UUID>&view=guide
```

`page` 可省略，不使用旧 `slide` 参数。Guide 使用与 TSX 文件名同名的命名导出，PPT 入口导出 `deck`，与当前 Shuku 保持一致。

## 检查与构建

```powershell
npm run typecheck
npm run build
```

类型检查覆盖播放器与预览入口；播放器库构建结果为 `dist/index.js`、类型声明和 `dist/style.css`。这不是课程发布包，也不是可直接部署的课程网站；课程源码 ZIP 通过 [course.pack](../references/engineering/delivery.md) 交付。

提交时保留 `src/`、`preview/`、`scripts/`、配置、`.env.example` 和 `package-lock.json`。已忽略 `node_modules/`、`dist/`、`.npm-cache/`、Vite/TypeScript 缓存、日志和本地环境文件。已有本地构建可以保留，Git 不会将它们纳入新提交。

## 常见问题

- **列表为空**：检查目标路径、课程 UUID 目录与 `outlines.json`；新增课程目录或修改配置后重启预览。
- **显式配置的 Shuku 运行时不存在**：确认 `SHUKU_ROOT` 下有 `packages/course-runtime/`，或使用 `--standalone` 启动。
- **素材加载失败**：素材放在课程 `assets/`，通过单参数 `moduleAssetUrl('真实相对路径')` 读取。
- **模型、评阅、训练不可用**：这些功能通过术库宿主 RPC 调用服务，要在 Shuku 学习页面验证；本地预览不模拟登录、GPU 或云端返回。
- **预览正常是否代表官网可用**：还须执行平台校验、真实构建及最终产物验收，本地源码预览不能代替官网验收。

`src/` 为播放器，`preview/` 为课程列表与装配入口，`scripts/` 负责发现课程。这里的修改不会回写 Shuku 或课程工程。
