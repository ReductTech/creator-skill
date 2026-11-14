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

禁止跨目录 `..`、磁盘路径、`file://`、手写 CDN 地址。新资源引用应使用固定相对路径；多个素材在代码数组中明确列出，不通过扩展名替换猜测文件。文件改名时修改引用本身，禁止建立格式映射兼容表。已有图片图集的坐标索引是内容数据，仍保留；不能以清理格式表为由删除图集裁剪、Canvas 或 WebGL 能力。

## 构建与 OSS 交付

1. 本地按真实相对路径读取资源。
2. 可信平台进程按配置处理图片，保留透明与动画效果，再对最终字节计算 SHA-256。
3. 以 `<配置前缀>/<哈希前两位>/<完整哈希>.<实际格式>` 上传 OSS；同字节复用，不覆盖不同内容。域名和桶配置只属于 Shuku，不写入课程。
4. 构建器自动注入该版本的资源交付地址，`moduleAssetUrl` 返回 SHA-256 OSS URL。版本内生成信息是平台构建输出，禁止让创作者手工维护或提交全局资源表。
5. 上传失败阻止交付。已发布版本不原地重写；源码保留相对路径。

GPU 构建容器保持断网，上传发生在容器外的可信 Worker，不将 OSS 凭据交给课程代码。只有明确配置为公开的静态素材才启用公共 OSS 上传；私有内容遵守原权限。HTML、交互代码及计算服务仍由服务器交付。GLTF 内部依赖按最终文件地址处理，图集坐标保持原语义。断网导出通过现有离线资源入口接管，不能假设 fetch(file://...) 可用。

正式术库缩略图保存在 `modules/<课程目录>/assets/scenedeck-thumbnails/`，统一为 `<scene-id>.webp`，1600×900 WebP，质量 q=20。由 `capture.thumbnails` 生成；运行时第一页同时自动生成 `assets/course-covers/<第一页ID>.webp` 的首页封面，同为 1600×900、q=20。无需传入尺寸或质量参数，评估截图仍为 1600×900 PNG。播放器 `assetId` 使用当前模块的 UUID，不使用目录名。

已有正式缩略图对应当前实现时可直接用于检查，无需重复截图；交互状态截图保存在 `_scratchpad/`。

## 构建、去重与发布

课程源码不再提供全局资源索引。平台从模块大纲发现课程与所属 assets，为每个构建版本自动生成产物清单。根目录 `asset-index.json`、`asset-formats.json` 及 Shared 旧资源索引会被拒绝；归属由课程目录发现，不维护全局登记或格式别名。

构建版本清单可记录 `path`、`sha256`、`size`、`mime`、`object_key`，用于去重、权限、完整性校验和恢复。这属于平台内部构建输出，不是全局映射表，也不是创作者的维护项。

哈希基于处理完成后的最终字节，不基于文件名、模块或 MIME。图片、视频、字体、JSON、模型及二进制素材都适用；对象键还包含规范化扩展名，保证不同 MIME 的字节相同文件分别交付。构建 JS/CSS 由平台保存为版本文件。相似画面但字节不同不会去重。压缩或转码后重新计算。每个版本保留自己的不可变清单，多个逻辑路径可引用同一对象。

术库按已发布或获授权预览的版本清单解析逻辑路径，只返回清单列出的已构建文件，按逻辑文件类型设置响应 MIME。保留 URL 目录层级，使 CSS、GLTF、模型纹理的相对引用正常；不要把页面里的所有 URL 直接替换为裸哈希 URL。公开课程素材由公共 OSS 对象交付；HTML、交互代码及私有内容由平台按版本与权限交付，不能因知道哈希绕过其访问控制。Shuku 展示端禁止读取源码。

本地 `dist` 在生成文件之间使用硬链接共享相同字节，文件树仍可独立部署；普通 ZIP 或复制到其他文件系统后可能重新占用空间。云端真正跨模块、跨版本去重由公共内容对象命名空间保证，与本地链接无关。

`assets.upload --module <UUID> --dry-run` 只读生成素材清单并统计唯一对象，不联系 OSS。执行真实上传需本次发布授权并传入 `--config <Shuku配置JSON绝对路径>`，读取同一份 `storage.oss` 配置，不在 Skill 另存桶地址或凭据。配置文件不可提交。默认扫描课程资源；`--module` 限定该模块拥有的 assets，共享依赖由正式构建的完整产物清单处理。显式 `--assets-dir` 的逻辑路径以该目录为根。

Shuku 的素材上传入口调用 `shared.asset_upload`；独立 Skill 的上传器使用随包保存的同一公共对象协议，素材使用与课件构建相同的 `shuku-oss/assets/sha256/<前两位>/<完整哈希>.<扩展名>` 公共目录及上传协议，不再写入按课程名组织的旧目录。上传器校验并复用已有对象，拒绝 `--overwrite`，不删除远端文件或源文件。`--records-only` 只接受 JSON；不再接受旧参数别名。真实上传传入 `--config` 指定统一 Shuku JSON，`--dry-run` 不读取 OSS 凭据或访问网络。上传返回的清单必须交给发布流程保存，单独上传素材不等于发布完整课程。

CAS 使用未开启版本控制的桶，读取桶状态后发现 Enabled/Suspended 就停止，不改桶设置。删除模块或版本不能直接删除共享对象；垃圾回收另行设计，此次不执行。

## 普通图片压缩

运行 `python creator-skill/scripts/tools.py assets.compress modules/<课程目录>/assets --dry-run` 先检查范围，移除 `--dry-run` 才执行。普通 PNG、JPEG、WebP 仅在长边大于 900 时处理：等比例缩到长边 900，另一边随比例缩小，输出 WebP q=80，不裁剪、不补边。长边小于或等于 900 的图片保持原字节和原格式，不重新编码。透明普通图片保留 alpha；动画、高位深图片、GIF、SVG 和其他格式跳过。

`assets/scenedeck-thumbnails/`、`assets/course-thumbnails/` 和 `assets/course-covers/` 使用独立标准：1600×900 WebP q=20，不受普通图片的 900 长边限制。正式截图本来为 16:9；旧缩略图迁移时非 16:9 图片等比例完整保留并居中补白。中间截图继续保留 PNG，不进入普通素材压缩。

生成 `.webp` 时保留原 PNG/JPEG，不覆盖已有同名 WebP；原文件已是大尺寸 WebP 时，先备份到素材目录旁的 `<目录名>-image-originals/` 再替换。`--report` 记录真实源文件、目标路径、前后尺寸、质量和字节数；`--dry-run` 仅输出计划，不写图片、备份或报告。格式和尺寸按上述标准执行，不以文件更小作为是否转换的条件。

改为 WebP 后使用独立的 `assets.rewrite` 同步静态和可验证的动态引用，使用真实 `.webp` 路径；参数、覆盖和未验证情况见[素材路径迁移](asset-paths.md)。压缩与路径迁移分开执行，不生成运行时格式映射表。源码中的原图与备份保留供检查和回退，批量迁移既有课件时核对引用后再决定是否清理。

实际压缩默认接着完成引用迁移与查漏，不等待用户再次提醒。按[压缩后的默认连续流程](asset-paths.md#压缩后的默认连续流程)保存本次转换报告，依次预览并应用 `assets.rewrite`、复跑确认无残留可迁移项、检查旧路径和动态来源，再验证受影响资源的真实加载；这整段完成后才按原流程清理临时记录并收尾。

转码后的最终字节重新计算 SHA-256，随新构建上传；旧发布版本保持不变，不自动删除其对象。Shuku 构建端的可选图片处理由平台自身实现，Skill 工具修改不代表平台已同步。
