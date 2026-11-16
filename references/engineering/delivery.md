# 源码 SKZIP 交付

只运行一次 Python 胶水入口，从输入目录连续走到源码包和最终汇总：

```powershell
python <Skill>/scripts/module/package_course.py "C:\course\modules"
```

也可使用 `python <Skill>/scripts/tools.py course.pack <目录>`，两者调用同一实现。仅依赖 Python 标准库和 Skill 自带的 Python 组件；不读 `target-root.json`，不需要 Shuku 工程或 `--shuku-root`。相对路径按调用目录解析。不提供 `--output` 参数。输出自动放在模块目录同级，结束时返回绝对路径。已有同名包或报告时自动使用 `-2`、`-3` 等后缀，不覆盖旧结果。

## 输入识别

| 输入 | 行为 |
|---|---|
| 模块目录，内有 `outlines.json` | 打包这一门 |
| 模块集合目录，直接包含多个模块 | 打包其中可通过源码检查的模块 |
| 工程根目录，内有 `modules/` | 从 `modules/` 识别模块 |
| 平铺工程，模块直接放在根目录 | 从直接子目录识别模块 |
| 一次传入多个目录 | 合并并去重，例如 `...package_course.py <目录A> <目录B>` |
| 上述目录中含 Shared，大小写不限 | 自动排除，不作为模块或依赖打入包 |
| 只传入 Shared 或没有模块 | 明确返回错误，不出空包 |

包内课程统一位于 `modules/<课程UUID>/`。Shared 由服务器提供；脚本不复制或改写 Shared。明确选择单个模块时，不自动扩张到其他未选择课程；外部字面量引用记录提醒。

## 自动输出位置

| 输入示例 | 默认包路径 |
|---|---|
| `C:/course/modules` | `C:/course/modules.skzip` |
| `C:/course`，内含 `modules/` | `C:/course/modules.skzip` |
| `C:/course/modules/<UUID>` | `C:/course/modules/<UUID>.skzip` |
| 平铺集合 `C:/lessons` | `C:/lessons.skzip` |
| 多个模块目录 | 模块父目录的共同位置下 `courses.skzip`；跨盘时使用第一个输入的父目录 |

同时在包旁保存同名 `.report.json`，例如 `modules.report.json`。失败时也尽量保存报告，包不存在则明确记录 `outputCreated: false`。

## 可复用的流水线组件

`package_course.py` 只负责编排和最终汇总，业务功能各自独立：

| 组件 | 职责与独立调用 |
|---|---|
| `source_inputs.py` | 识别目录、选择文件、排除 Shared、缓存、`_scratchpad`、本地 `.env` 和已有归档；`tools.py course.discover <目录>` 可独立运行 |
| `source_checks.py` | 复用 Python 元数据规则，检查 UUID、页身份、已声明入口、UTF-8；报告字面量引用；`tools.py course.inspect <目录>` 可独立运行 |
| `source_images.py` | 检查 PNG/JPEG/WebP 等图片文件头，统计格式和不匹配项；`tools.py course.images <目录>` 可独立运行 |
| `source_archive.py` | 对已收集的清单流式归档、计算 SHA-256、写入清单、校验最终包并原子交付；可由其他 Python 工作流直接调用 |
| `source_report.py` | 汇总各阶段耗时、详细错误与提醒，保存报告并生成用户决策建议；不自行询问或上传 |
| `common/skzip.py` | 封装与完整性校验，可独立调用 `verify_archive(path)` |

流水线只收集一次文件清单，在组件间传递，不预先再跑一轮独立检查。用户只要求打包时，不单独调用上表中的检查命令，不执行清理，不改源码，不进行资源确认。正式资源默认全部保留。请求范围内有严重错误时，整次打包停止，不静默跳过坏模块。普通提醒不中断流程，不要求提前确认；包生成后再由智能体根据最终报告与用户对话。

## 本地检查的边界

- 本机不安装 Node、npm、Pillow、Playwright 或其他依赖，不执行课程源码，不编译、不构建、不渲染、不截图，不启动服务。
- PNG/JPEG 只按文件头识别并统计，PNG 另核对 IHDR 和正尺寸；这不是完整图片解码验证。不自动转 WebP、不重新压缩图片、不改引用、不补编辑 ID。
- 图片文件头异常、无法确定的引用和缺失缩略图作为提醒。已有缩略图随源码保留，缺失不阻止源码出包。
- 仅做元数据、源码编码、入口和路径等静态合法性检查，不声称 JavaScript 语法、类型、可运行性或恶意程度已获认证。
- 拒绝符号链接/junction、越界或重复包路径、超限文件、打包时被修改的文件。大小限制为展开后 1 GiB、单文件 128 MiB、文件数小于 10000。
- 文本使用低开销 ZIP 压缩，图片、视频、模型等二进制资源直接存储，不重复转码。写包时流式计算文件哈希，最后只核对实际成包完整性；不重复读取工程来执行前面的业务检查。

## 清单与服务器职责

根目录 `skzip-manifest.json` 保留 SKZIP 容器格式 `shuku-skzip` / schema 1，使用源码策略 `creator-source-v1`。每个文件登记路径、大小和 SHA-256。清单明确标记 `packageKind: source`、`sharedPolicy: server-provided`，只为实际执行的本地源码与路径检查记录通过。

分类、恶意代码审查、平台导入、服务器构建与渲染列入 `serverPending`，相应检查状态为 `server-pending`，不得填写虚假的本地通过结果。默认保留原始正式资源，无作者资源审批字段或等待步骤。

Python 和随 Skill 提供的浏览器完整性校验器均支持源码策略，并继续兼容历史 delivery-v1/v2 包。服务器上传端也须支持此源码策略、提供 Shared 并独立完成其职责；本 Skill 的修改不会自动更新服务器。旧上传端可能拒绝新策略，不能声称已通过官网验收。

## 结束、严重程度与用户对话

stdout 仅输出一份详细 JSON，同时写入同级 `.report.json`。报告包含 `inputs`、实际 `output` 和 `reportPath`、`outputCreated`、模块与文件清单汇总、原始与压缩大小、图片统计、排除的 Shared、各 `stages` 的状态与耗时、`issues.serious`、`issues.warnings`、`coverage`、`serverPending`、总耗时和 `agentNextAction`。`summary` 提供便于面向用户说明的数字。不得只返回包路径或笼统的“成功”。

- **普通提醒**：PNG/JPEG 格式或文件头提醒、缺少缩略图、无法确定的字面量引用、大纲草稿等。允许正常出包；`uploadEligible: true` 仅表示本地满足提交条件，不表示服务器已接受。智能体先告诉用户输出位置和提醒，再询问“修复后重打，还是按当前状态上传？”用户可以接受提醒并直接上传。
- **严重错误**：非法身份或元数据、已声明入口缺失、非法源码编码、链接/越界路径、重复路径、大小超限、源文件打包时被修改、读写失败或包完整性失败。阻止整次出包，`uploadEligible: false`，不可忽略后上传。智能体说明具体文件、错误与修复方案，与用户沟通后修复并重新运行入口；修复完成后确认上传。
- **没有提醒**：显示输出位置、范围和大小，然后确认上传。

脚本不阻塞等待人类输入，也不上传；它返回 `userOptions`、`userPrompt` 和 `requiresUserConfirmation` 供智能体组织对话。`uploadAuthorized: false` 表示脚本自己不授予上传权限；智能体应结合当前会话中的授权。用户已经明确接受当前包的提醒并授权上传时，不再重复确认；不能把一般性的“允许有提醒出包”当作上传授权。严重错误修复后的新包须再确认上传。

退出码 0 为已生成完整源码包（可以有普通提醒），1 为严重源码错误导致未出包，2 为输入或执行错误。失败也返回阶段与具体原因，供智能体沟通修复，不擅自连续重试。不默认上传或发布。
