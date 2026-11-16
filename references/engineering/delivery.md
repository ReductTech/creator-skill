# Python / Pillow SKZIP 交付

一次运行 `python <Skill>/scripts/module/package_course.py <输入目录> [更多目录]`；或 `tools.py course.pack <目录>`。只使用 Python、Pillow，允许必要的轻量 Python 包，绝不安装或调用 Node/npm。无图片时标准库即可；需要图片加工而缺少 Pillow 时，明确报告依赖，不偷偷跳过。打包不执行课件代码，不构建、不截图、不补编辑 ID、不改写引用、不上传。

## 输入与输出

支持模块本身、模块集合、带 modules/ 的工程和平铺工程，多个输入合并去重。包内课件统一位于 `modules/<UUID>/`。输出自动位于输入集合或模块同级；多输入使用共同父目录下 courses.skzip，跨盘使用第一个输入的父目录。不读 target-root.json、不需要 Shuku、无 --output；已有包或报告时递增编号，不覆盖。

平台标准 Shared 由服务器提供，不重复上传。明确选择的自定义风格从工程 course-styles.json 收集，以 styles/<风格UUID>/ 和登记表交付；缺依赖或默认风格冲突报严重错误。作者原工程与 Shared 均不修改。缓存、_scratchpad、node_modules、dist、.git、已有归档不入包。

## 文件规则

规则定义在 scripts/common/submission_policy.py，与服务器对应模块保持一致。

1. 黑名单优先：shell、PowerShell、批处理、系统可执行文件、动态库、Python 字节码等扩展名，.env / .env.*、shell 启动文件，以及伪装的 ELF、PE、Mach-O 与危险解释器 shebang，均不入包。扩展名不区分大小写，.so.* 同样禁止，放入 assets 不豁免。课件和自定义风格中的禁用文件只排除，不删除本地文件；逐项给出 FILE_EXCLUDED 警告并继续打包。已知字面量依赖被排除文件时给出 EXCLUDED_FILE_REFERENCED 警告，提示后续构建或运行可能失败，不因此终止打包。动态依赖留待服务器完整检查，不声称本地已证明无依赖。
2. 源码白名单 .ts/.tsx/.js/.jsx/.mjs/.cjs/.css，以及准确根路径 outlines.json、风格根路径 style.json 元数据，允许超过 100 KiB 留在 assets 外，仍受单文件上限约束。
3. 其他文件包括普通 JSON：超过 102400 字节必须放在所属课件或风格的 assets/。等于限制允许在外。违规报严重错误，不自动搬移、不擅自修改源码引用。
4. 链接/junction、越界与重复路径、非法源码编码、身份或已声明入口错误、超限和完整性错误阻止出包。保持 1 GiB 总量、128 MiB 单文件、少于 10000 源码文件限制。
5. `.py` 源码和 `.bin` 数据允许入包，每个文件产生 `HIGH_RISK_FILE` 警告并标记 `riskLevel=high`；它们不属于超限源码白名单，超过 100 KiB 必须放在所属课件或风格的 `assets/`。Python 源码可保留 Python shebang，但 `.py` / `.bin` 都不能豁免原生可执行内容和 shell shebang 禁令。报告和包清单保存 `highRiskFiles`，包整体标为高危，服务器安全检查仍为待执行。本地仅存储和检查，不执行这些依赖；扩展名及文件头检查不保证代码无害或容器不会被穿透，服务器仍须独立审核并在受限环境中运行。

本地字面量依赖检查只对收集到的文件清单做路径规范化和匹配，不把任意源码字符串传给文件系统解析。匹配时去除 `?raw` 等查询和片段；相对导入按源码所在目录定位，`moduleAssetUrl()` / `moduleJson()` 按课件 `assets/` 定位。已排除文件仍按上述黑名单规则处理，不因运行时使用而自动放行。

## 本地图片加工

入口在临时目录生成图片，不修改原图。对课程 assets 下普通 PNG/JPEG/WebP 完整解码；不放大，等比限制到宽 1600、高 900，输出 WebP q=80，保留透明。合格 WebP 原字节复用；无需缩放且编码反而变大时保留原图。动画、高位深、图集、目标冲突及无法安全转换者保留原样并报告，服务器继续处理。缩略图不在本地生成，也不因缺失报警。

成功转换后包内只放实际新图；作者原图留在电脑上。源码仍保留原引用，imageConversions 登记旧路径、新路径、原图摘要与大小、新图 SHA-256/大小/宽高及加工参数。同路径 WebP 缩放也记录。不能把转换后缺原图的包冒充立即可构建源码。

## 两端契约

清单使用固定的 `shuku-skzip` 容器与文件清单，不再生成或按 policy、schema、filePolicy 的版本标签拒收。历史包中的 V1/V2 等标签仅作为兼容元数据忽略；无标签的包同样按实际内容验证。接收条件是清单结构、路径、大小、文件哈希以及真实内容符合官方当前规则。Python、浏览器和服务器使用同一原则；客户端报告不是服务器安全或构建的通过凭证。高风险文件由服务器独立识别，已有声明则检查其与实际清单一致。公开 workflowTag 是完整性约定，不是防伪认证。

网页校验器按实际内容接受新旧包，历史版本标签不影响接收。服务器独立复核完整性、文件政策、转换范围及实际 WebP；在无凭据、无网络的入库隔离进程中迁移引用，然后才做资源完整性与平台源码检查。无法可靠迁移时明确失败，不构建残缺课件。服务器补编辑 ID、冻结源码、构建、处理未达标资源、截图并审核；图片格式尺寸达标不证明具体 q 值，本地报告也不能免除服务器检查。

## 报告与作者决策

stdout 返回一份 JSON；包旁保存 .report.json 和 .report.md。通过项仅给出数量和统计范围，不逐项展开。警告、严重错误逐项含 code/path/message/impact/repair/recheck，已知行号、大小、阈值也记录。阶段耗时、转换统计、节省字节、排除文件和输出位置保留。报告体积超限不得静默截断包清单。

严重错误阻止整个请求出包，不静默跳过坏课件；作者决定修复或调整范围后重试。警告允许出包，由作者决定修复重打或接受当前包提交。已有覆盖本包与提醒的明确上传授权不重复询问。脚本只报告建议，不上传、不自行替用户决定。

## 组件

source_inputs.py 识别和收集；source_checks.py 检查源码与文件政策；source_styles.py 收集自定义风格；source_prepare.py 用 Pillow 优化图片；source_archive.py 流式归档并验包；source_report.py 汇总；common/skzip.py 定义封装。course.discover / course.inspect / course.images 仍可独立只读调用，但正常出包只调用一次 course.pack。
