# 素材引用路径迁移

`assets.rewrite` 只修改所选课件中的引用文本，不压缩、转码、移动、改名或删除素材；不修改 Shared。目标文件必须已经存在于该课件的 `assets/`。不需要 Pillow、浏览器或网络，使用 Node.js 和 TypeScript 解析源码；TypeScript 可来自目标工程、内置 Player Preview 的依赖或 `SHUKU_ROOT`。缺少时在 `player-preview/` 执行 `npm ci`，可用 `environment.doctor --tool assets.rewrite` 检查。

## 压缩后的默认连续流程

用户要求实际压缩课件图片时，智能体默认把压缩、引用迁移和遗漏检查作为同一任务连续完成，不在图片生成后结束，也不等用户再次要求改引用。两个工具保持独立，通过本次转换报告衔接；不把迁移实现塞进压缩工具。用户明确只做 dry-run、只检查或另有限制时，以其要求为准。

1. **确认范围并预览压缩。** 读取 targetRoot，定位本次课件或指定素材子目录，只处理任务范围；不改 Shared。为本次操作选择独立的模块 `_scratchpad/asset-processing/<操作ID>/`，保存报告，避免覆盖尚需使用的历史转换记录。
2. **实际压缩并保留记录。** 执行 `assets.compress <本次素材目录> --report <本次compression.json>`，核对返回状态及每张图片的 converted/skipped 原因。后续直接使用该报告，不根据扩展名批量猜测，也不让 skipped 小图跟着改路径。已有同名 WebP 等跳过项需要核对，不能当成这次已成功转换。
3. **预览并应用引用迁移。** 紧接着执行 `assets.rewrite --module <UUID或alias> --changes <同一compression.json>`，查看 changedFiles、matches、unresolved 和 unverified。计划明确且在已授权任务内时直接加 `--apply` 执行，并可保存迁移结果；不再要求用户重复确认。unresolved 会阻止工具写入，智能体应检查具体调用点、数据列表和素材，修复后重跑；不为迁就整个动态拼接而压缩无关图片，也不误改未转换素材或引入运行时格式别名表。
4. **复跑查漏并检查资源引用。** 用同一转换报告再次运行只读 `assets.rewrite`，要求 changedFiles 为空、referenceCount 为 0、unresolved 为空；执行 `check.asset-imports --module <UUID>`，并按影响范围执行 `check.module --module <UUID>`。静态检查通过仍不足以排除旧文件保留时的漏改：依据报告中的旧路径和文件名，用 `rg -n -F` 搜索课件源码残留，逐处区分有效引用、说明文字和测试样例；追踪动态模板、拼接、helper 调用及外部数据，不能只搜完整字面量路径，也不对所有 `.jpg` / `.png` 做全局替换。
5. **验证实际加载并收尾。** 逐项核对 unverified 的调用点与数据来源，记录判断和验证证据；工具可能仍报告通用 helper，人工核对记录不能被说成工具已静态证明。按变更范围验证真实页面及相关状态，覆盖 CSS 背景、缩略图切换、Canvas/WebGL 纹理和其他实际消费者，检查失败请求与图片解码/加载。确认完成前保留原图、转换报告和源码备份，不先清理 `_scratchpad`。必要记录另存后，按原有流程清理临时目录，再交付或提交。

下面以 `modules/<UUID>/` 布局说明各独立命令的衔接；平铺工程和素材子目录按实际路径替换。逐条检查返回结果，失败时先处理具体问题再继续，不把整段命令当成忽略错误的流水线：

```powershell
$assetSkillPath = '<Skill绝对路径>'
$assetModuleId = '<课程UUID或alias>'
$assetModulePath = 'modules/<课程UUID>'
$assetRunId = [guid]::NewGuid().ToString('N')
$assetReportDir = "$assetModulePath/_scratchpad/asset-processing/$assetRunId"

python "$assetSkillPath/scripts/tools.py" assets.compress "$assetModulePath/assets" --dry-run
python "$assetSkillPath/scripts/tools.py" assets.compress "$assetModulePath/assets" --report "$assetReportDir/compression.json"
python "$assetSkillPath/scripts/tools.py" assets.rewrite --module "$assetModuleId" --changes "$assetReportDir/compression.json"
python "$assetSkillPath/scripts/tools.py" assets.rewrite --module "$assetModuleId" --changes "$assetReportDir/compression.json" --apply --report "$assetReportDir/rewrite.json"
# 再次只读检查，应无剩余可迁移引用；unverified 仍须逐项核对
python "$assetSkillPath/scripts/tools.py" assets.rewrite --module "$assetModuleId" --changes "$assetReportDir/compression.json"
python "$assetSkillPath/scripts/tools.py" check.asset-imports --module "$assetModuleId"
python "$assetSkillPath/scripts/tools.py" check.module --module "$assetModuleId"
# 随后搜索旧路径残留，并验证受影响页面和动态资源的实际加载
```

本次没有 converted 记录时，不能据此认定历史引用已经迁移。若存在已生成的目标图或此前未完成的迁移，复用对应的历史转换记录；记录缺失时可用下方 `--to-ext` 只读预览并核对关联后处理，不覆盖现有目标图来伪造一次新转换。

完成时简述实际转换、改引用和查漏的结果，以及真实加载覆盖范围；仍有未解决引用或无法验证的动态来源时明确指出，不能仅凭 changedFiles 为空或压缩命令退出 0 就宣称全部完成。只有确实缺少必要信息或外部条件时，才向用户说明具体阻碍。

## 从已完成的转换记录迁移

```powershell
# 默认只读；相对参数以 targetRoot 为基准，不受当前终端目录影响
python <Skill>/scripts/tools.py assets.rewrite --module <UUID或alias> --changes modules/<UUID>/_scratchpad/compression.json
# 核对报告后，按任务已有授权应用
python <Skill>/scripts/tools.py assets.rewrite --module <UUID或alias> --changes modules/<UUID>/_scratchpad/compression.json --apply
```

`--changes` 接受 `assets.compress --report` 的转换记录，包括旧版顶层数组和新版 `images` 数组；仅使用 `status: converted` 的记录，跳过小图等未转换素材。也可提供下面的对象，或 `{source, target}` / `{from, to}` 数组；路径相对于该课件 assets，绝对路径也必须位于其中。源文件可已删除，目标文件必须存在；拒绝冲突和串联替换。

```json
{
  "images/diagram.png": "images/diagram.webp",
  "course-thumbnails/intro.jpg": "course-thumbnails/intro.webp"
}
```

这份 JSON 是一次操作的输入或转换报告，不是课件运行时映射，不应随源码提交为全局别名表。

## 从已有目标文件发现扩展名变化

```powershell
python <Skill>/scripts/tools.py assets.rewrite --module <UUID> --to-ext webp
python <Skill>/scripts/tools.py assets.rewrite --module <UUID> --to-ext webp --from-ext png,jpg,jpeg --apply
```

它按已有 WebP 文件发现同目录、同主文件名的旧引用；即使旧图已移出 assets 也可使用。只转换了部分素材、存在历史同名目标或需要跨目录/改主文件名时，优先使用明确的 `--changes`，避免把无关旧引用关联到现有文件。此步骤不生成目标图片。

## 覆盖范围

| 引用形式 | 处理方式 |
|---|---|
| JS/TS/JSX/TSX 的 import、export、动态 import、require、new URL、JSX 属性、对象及数组中的字符串 | 解析语法并匹配完整路径；注释、远端 URL 和整段说明文字保留 |
| `moduleAssetUrl('images/a.jpg')` 与常见 helper 的短路径参数 | 使用真实 assets 路径；短路径必须能唯一定位，不能仅凭重名文件猜测 |
| `` `images/${item.id}.jpg` ``、`'images/' + id + '.jpg'` | 检查已知素材组，完整迁移到同一目标扩展名才修改 |
| 字符串 `.concat()`、字面量数组 `.join()`、`path.join()`、局部 const 字符串、条件分支 | 静态解析；保留未知插值及其运算，不运行课程函数 |
| `import.meta.glob('./assets/**/*.jpg')` | 按 glob 匹配整个素材组；`**/` 包含当前目录和子目录 |
| CSS `url()`、JSON/glTF 字符串、HTML `src`/`href`/`poster`/`srcset`、JSX `srcSet`、Markdown 图片与链接 | 按对应结构更新路径，保留 query、fragment、srcset 描述符、注释及 Markdown 代码围栏 |

相对源码路径、课程 assets 相对路径和带明确 assets 前缀的路径均可匹配。静态引用支持改主文件名和目录；动态族只自动处理主文件名与目录保持一致的扩展名变化。

动态匹配基于本次已知资产和转换记录，不推断运行时可能产生的所有 ID。动态组中有未转换文件、短路径歧义、未知目录前缀或不同目标扩展名时，`unresolved` 给出文件、行号、表达式和原因，退出 `1`；即使带了 `--apply`，整次操作也不写入。不要为了通过检查删除未转换的正式素材。

任意函数计算、运行时外部数据、任意 `.replace()` 或复杂封装不能普遍静态求值。识别到无法求值的 `moduleAssetUrl(...)` 时列入 `unverified`，需要检查调用点或数据来源；它不会被当成已验证引用，也不会阻止其他已确定引用的迁移。CSS 转义、自定义模板标签、HTML 脚本块等复杂语法需另行核对。工具不承诺覆盖所有程序表达式。

## 写入与验证

默认或 `--dry-run` 不写源码、备份或报告。结果包括 `changedFiles`、`referenceCount`、逐处 `matches`、`unresolved`、`unverified` 和 `applied`。参数/目标文件/源码语法错误退出 `2`。

`--apply` 写入前重新检查路径边界和源码版本，备份到模块 `_scratchpad/asset-paths/<操作ID>/`，保留 UTF-8 BOM 和原换行；临时文件替换失败时回滚已经写入的文件。无变化时不创建备份。可用 `--report modules/<UUID>/_scratchpad/asset-paths-result.json` 保存 JSON 结果；报告仅在成功应用后写入，并限定在该课件 `_scratchpad`。需要长期保留的备份或记录在清理临时目录前另行保存。

迁移后检查 `check.asset-imports --module <UUID>`，按变更范围验证真实页面和交互，特别是动态缩略图、CSS 背景与 Canvas 素材。源码静态迁移成功不等于平台构建或浏览器加载已通过。相关工具回归测试为 `node --test scripts/tests/rewrite_asset_paths.test.mjs`。
