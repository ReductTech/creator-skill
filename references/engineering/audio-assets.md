# 音频准备

普通课件音频在作者本地统一为 `.m4a` 容器、AAC-LC 编码，默认目标码率 96 kbps。默认针对口播、讲解和普通音效；音乐需要更高保真时可用 `--bitrate 128` 或 `160`，以实际试听为准。96 kbps 约为每分钟 0.72 MB，另有少量容器开销；目标码率不是严格的文件大小上限，短音频、静音等内容的实际码率可能不同。

保留单声道或双声道；多声道降混为双声道并提示。采样率不超过 48 kHz，不提高低采样率输入，选择不超过源采样率的 AAC 支持值。不裁切首尾、不删静音、不改变播放速度，也不自动做响度归一化。音频转码有损，尽量从 WAV/FLAC 等原始素材一次生成，避免反复压缩已压缩成品。

## 调用

需要 Python 3.10+、FFmpeg（原生 AAC 编码器）和 ffprobe，不安装或下载依赖。相对路径以调用时的工作目录为准，不读取 `target-root.json`。

```powershell
# 默认只探测和列出计划，不生成文件。
python <Skill>/scripts/tools.py course.audio "D:\课程\assets"

# 批量转码，保留子目录结构，原文件不覆盖。
python <Skill>/scripts/tools.py course.audio "D:\课程\assets" --apply --output "D:\课程\_scratchpad\audio-aac"

# 单文件或自定义质量，依赖不在 PATH 时可明确指定。
python <Skill>/scripts/tools.py course.audio "D:\原稿\配乐.flac" --apply --bitrate 128 --output "D:\课程\_scratchpad\audio-aac" --ffmpeg "D:\ffmpeg\bin\ffmpeg.exe" --ffprobe "D:\ffmpeg\bin\ffprobe.exe"
```

支持 WAV、MP3、M4A、AAC、FLAC、OGG/Opus、AIFF 等常见音频。默认输出到输入目录（单文件时为所在目录）的 `_scratchpad/audio-aac/`；文件名为 `<完整原文件名>.compressed.m4a`，保留原扩展名避免同名冲突。递归跳过 Shared、`.git`、`node_modules`、`_scratchpad`、指定输出目录、链接及 junction；显式输入/输出也不能指向 Shared 或链接路径。

只保留第一条音轨，多音轨会提示；封面、章节、歌词和其他附加元数据不写入成品。检测到实际视频画面则拒绝，改用 `course.videos`，不自动丢弃视频。视频内音频继续由视频工具一并编码。

默认 stdout 为单份 JSON、进度写 stderr；执行或单文件错误返回 2，仍继续处理批次的其他文件。已有输出报错、不覆盖、不假定旧文件有效；可用新的 `--output` 重试。每个结果通过实际编码、声道、采样率、时长和完整解码校验后，才原子创建目标文件；失败/中断清理当前未完成结果，保留已完成文件和原片。与视频工具一样，目标文件系统需支持同卷硬链接。

## 进入课件

试听代表性片段，检查人声清晰度、音乐失真、开头结尾和音量。技术校验不能证明听感；转码也不保证比已经高效压缩的原文件更小，工具会报告体积未减小的结果。

将选定成品复制进课程正式 `assets/`，更新 TSX/JSON 等完整字面量引用，避免源音频和成品同时进入交付包。原始录音保留在包外；确认成品已提升并更新引用后，再按既有规则清理 `_scratchpad`。工具本身不修改引用、不上传、不在 `course.pack` 或服务器端自动执行，也不新增平台上传格式或大小限制。

实际压缩任务必须继续核对路径：结果 `source` / `output` 是绝对路径，`source_relative` / `output_relative` 分别相对本次输入根目录和输出根目录，不能直接当作课件资源引用。`output_exists` 确认本次成品存在，`temporary_output` 标明是否仍在 `_scratchpad`；`reference_status` 始终提示还需提升和检查引用。按源→输出映射逐项将选定成品放进本课件正式 `assets/`，核对复制后字节一致，更新完整字面量路径并搜索旧路径和旧文件名残留，检查实际消费者与动态数据。课程引用统一使用 `/`，不写本机绝对路径或 `_scratchpad` 路径。未完成引用核对不能宣称课件已完成；实际播放未验证时单独说明。

编码参数依据：[FFmpeg 原生 AAC 编码器](https://ffmpeg.org/ffmpeg-codecs.html#aac)。
