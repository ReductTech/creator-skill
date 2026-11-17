# 模块身份与资源

## 模块 UUID

新建模块默认使用目录 `modules/<UUID>/`，`outlines.json.id` 与 `moduleIdentity.id` 必须等于目录 UUID（标准小写 UUID v4）。标题与 `alias` 可读，改标题、内容、页序不改变 UUID。每页 `pages[].id` 使用独立的标准小写 UUID，新增页面生成 UUID v4；保留已有合法页面 UUID。文件名与语义页目录无需使用 UUID。不增加独立的 `uuid` 页面字段或版本链。

```json
{"id":"2e5c4732-a40a-4d20-b954-a61507aabc75","moduleIdentity":{"version":1,"id":"2e5c4732-a40a-4d20-b954-a61507aabc75"}}
```

示例不能直接作为新课身份。`module.init --title "课程标题"` 自动分配 UUID，或用 `--directory <UUID>` 指定。只创建缺失大纲，不覆盖已有文件。`module.identity --check` 只读检查；不加 `--check` 可补齐缺失身份；UUID 目录使用目录 UUID，只在 UUID 目录补齐缺失身份；非法或冲突时停止，不擅自改写稳定身份。

复制为独立新模块时分配新的目录 UUID，同步大纲 id、moduleIdentity.id、path 和运行时 assetId，再核对引用。不要沿用源模块身份。素材文件可以保留原名与字节，上传后自然复用同一 SHA-256 对象。Git 记录整个模块的版本，UUID 不代替 Git 提交。

Shuku 不接受非 UUID 课程目录。旧语义目录需显式迁移目录、id 与引用，保留合法的页面 UUID；不以兼容模式绕过。工程可使用 `modules/<UUID>/` 或根目录 `<UUID>/` 的单一布局。

## 复制内置 Shared

本 Skill 根目录自带完整的 `shared/` 风格包。初始化课程工程或目标缺少 Shared 时，智能体直接复制这份目录，不要求用户另外寻找、下载或手工复制。

1. 以 `target-root.json.targetRoot` 为目标根目录。`modules/<UUID>/` 布局复制到 `<targetRoot>/modules/shared/`；已有平铺 `<UUID>/` 布局复制到 `<targetRoot>/shared/`；空工程默认采用 `modules/` 布局。
2. 复制整个 `<Skill根目录>/shared/`，包括 `style.json`、`bootstrap.ts`、`react/`、`assets/`、`types/` 与 `vendor/`，保持目录层级。目标已有 Shared 或已登记同一风格 UUID 时复用现有包，不覆盖或重复登记。
3. 原样使用内置包时保留 `style.json.id`，不因复制而生成新 UUID。不存在 `course-styles.json` 时，Shuku 可从标准位置的 `shared/style.json` 自动发现；已有登记文件时补齐对应 `styles[].id/path`，保留其他风格与既有选择。
4. 课程组件通过 `@shuku/course-style/react` 使用复制后的 Shared；资源、请求与状态仍从 `@shuku/course-runtime/react/...` 导入。复制 Shared 不代替 Shuku 构建环境。独立新风格按下方 UUID 规则处理。

## Shared 风格 UUID

本 Skill 的 Shared 为只读依赖，不允许修改；允许原样复制并保留 UUID。以下风格身份规则用于理解和校验已有风格包，不构成修改 Shared、创建分叉或覆盖现有包的授权。

Shared 作为风格包时，在包根目录的 `style.json` 中用 `id` 保存风格 UUID。工程常见位置为 `modules/shared/style.json`；平铺工程也可使用 `shared/style.json`。字段名是 `id`，不另加 `uuid` 字段，也不把目录改名为 UUID。风格 UUID 与课程 UUID、页面 UUID 分开管理，不互相代用。

```json
{
  "schema": 1,
  "id": "58ce8cde-ea71-4afb-bb25-6cbaad0203ea",
  "name": "我的独立风格",
  "protocol": 1,
  "bootstrap": "index.ts"
}
```

以上 UUID 仅用于说明格式，不能直接作为新风格身份。创建独立风格时用 `str(uuid.uuid4())` 生成一次标准小写、带连字符的 UUID v4，并保存到 `style.json.id`。`bootstrap` 和可选的 `presentation` 指向包内实际存在的入口，按实际工程填写，不照抄不存在的文件。

| 操作 | UUID 规则 |
| --- | --- |
| 原样使用平台默认 Shared | 保留默认 UUID `76018445-20ab-4dd9-9543-385d177eb159`；未随 ZIP 携带默认包时由 Shuku 补齐 |
| 同一套风格修复、调整或升级 | 保留原 UUID；改名、移动目录或再次打包也不重新生成 |
| 多门课程复用同一套风格 | 复用风格 UUID，各课程仍保留各自的课程 UUID |
| 从默认或其他风格复制出独立新风格 | 分配新的风格 UUID，不沿用原风格身份；即使暂时字节相同，也按独立风格处理 |

同一份源码中，同一个风格 UUID 只登记一个风格包。存在 `course-styles.json` 时，对应 `styles[].id` 必须与包内 `style.json.id` 一致，`styles[].path` 指向该包目录；`default_style` 和课程大纲中显式填写的 `style_id` 引用对应 UUID。更换为独立新风格时同步这些引用，不改变课程身份；同一风格更新时保留这些身份引用。风格归属或使用权限冲突按平台报错处理，不覆盖他人的风格登记。

风格身份采用 UUID 约定：同一 UUID 就按同一套风格处理，不根据名称、目录、代码差异或 SHA-256 自动判断它是否已经变成另一套风格。同一 UUID 下修改内容是否兼容，由创作者自行维护并承担影响；Skill 不额外设计内容比对、风格分叉确认或要求用户在网页上重复选择。创作者决定另立一套风格时，才按上表分配新 UUID。风格包需保留完整的自定义组件及依赖，平台默认补全不能替代缺失的自定义代码。

这个约定只限定风格身份判断。平台原有的 SHA-256 资源去重、完整性校验、构建快照与历史版本保留继续生效；不让创作者手工计算风格哈希或维护 `style_revision`，也不为本规则新增后端判定机制。

## 正式资源与中间产物

课程专属图片、视频、字体、图标、3D 模型、外部数据文件和术库缩略图放本课程目录 `modules/<课程目录>/assets/`。`moduleIdentity.id` 来自当前模块的 `outlines.json`；代码内定义的课程数据随模块实现保存。

真正跨模块共用的正式素材放在 `modules/shared/assets/`；Skill 自身的设计参考图仍保留在 `creator-skill/assets/`。新素材不再写入仓库根目录的 `assets/<UUID>/`。平台工具不再回退读取旧根目录素材，使用前迁移到课程 assets 并修正引用。

设计图、试制素材、检查截图与报告等逐页中间产物放在 `pages/<语义页目录>/_scratchpad/`。课程整体原稿提取和汇总资料放在模块级 `_scratchpad/`，两者均不上传到资源 CDN。确定用于正式页面的素材再放入 `modules/<课程目录>/assets/`，实现不得引用 `_scratchpad/` 中的文件。

## 资源引用：平台强制约定

资源统一通过 `moduleAssetUrl` 管理。用户只写相对于本课程 `assets/` 的真实路径，不写 OSS 地址、SHA-256、电脑绝对路径、网站根路径或历史文件别名。

```tsx
import { moduleAssetUrl } from '@shuku/course-runtime/react/assets';
const imageUrl = moduleAssetUrl('images/example.jpg');
export function Lesson() { return <img src={imageUrl} alt="模型结构" />; }
```

课程上下文由构建器注入。`moduleAssetUrl` 与 `moduleJson` 只接受一个课程内路径参数；旧显式模块 ID 必须改写。资源从 `@shuku/course-runtime/react/assets`、JSON 从 `@shuku/course-runtime/react/moduleJson` 导入；Shared 不再转发内核接口。CSS 背景图使用 helper 生成地址后传入 CSS 自定义属性；Canvas、WebGL 与音视频也消费该 URL，不另建路径解析器。资源 JSON 按需 fetch 此地址，不打入 JS 包；可复用 `moduleJson` 的缓存、并发合并和重试。

禁止跨目录 `..`、磁盘路径、`file://`、手写 CDN 地址。**素材路径不得拼接字段。** 新建或修改素材引用时，每项都必须写出相对于本课程 `assets/` 的完整固定路径，包含目录、文件名与扩展名；不得通过模板插值、`+`、`.concat()`、`.join()`、`path.join()` 或扩展名替换拼出素材路径，也不得手工拼入模块 UUID 或只存裸文件名后再补目录，以免寻图失败、同名素材歧义或格式转换后漏改引用。动态切换图片时，从明确列出的完整路径中选择，再将所选路径原样传给 `moduleAssetUrl`；JSON 等其他素材引用同样适用。文件改名时修改引用本身，禁止建立格式映射兼容表。已有图片图集的坐标索引是内容数据，仍保留；不能以清理格式表为由删除图集裁剪、Canvas 或 WebGL 能力。

例如，切换图片时将完整路径直接存入数据：

```tsx
const thumbnails = [
  { path: 'workflow/course-thumbnails/weight-sharing.webp', label: '权重共享' },
  { path: 'workflow/course-thumbnails/window-scan.webp', label: '局部匹配' },
];
// 路径须对应真实存在的文件；数据字段原样传入，不再拼接目录或扩展名。
const images = thumbnails.map(item => (
  <img key={item.path} src={moduleAssetUrl(item.path)} alt={item.label} />
));
```

## 交付与平台职责

交付运行 [course.pack](delivery.md)，自动准备图片、音视频并迁移临时副本引用。正式图片为 SVG/WebP，SVG原样保留；转换参数、动态引用和失败处理只在交付文档维护。原工程不修改。

Shuku 根据实际文件字节计算 SHA-256、保存不可变版本与资源清单并处理权限。作者只维护真实相对路径，不填写对象键、桶地址、哈希表或构建收据。正式截图与缩略图由平台从当前发布版本生成；已有本地缩略图只能作相应版本的检查参考。缩略图的课程内位置为 `assets/shuku-thumbnails/<页面UUID>.webp`，1600×900、q20；检查截图不是正式缩略图。

默认 Shared 不入包，由平台提供；明确登记的自定义风格及其依赖保留。Skill的Shared只读规则不因平台支持自定义风格而解除。真实素材上传是独立开发者工具，需要已有授权和明确配置，不是普通作者打包流程。

需要在作者原工程中实际压缩、改名或迁移时，读[路径迁移](asset-paths.md)；工具报告中的未验证项不能当作真实加载通过。
