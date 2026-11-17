# 第三方来源与许可证

本地精裁工具基于 CutFrame 的设计进行定制；时间数字校验函数改编自其 parse_seconds，其余共享素材库、SQLite、精裁发布与单条合成模块为本次实现。

- 来源：https://github.com/V0ightt/CutFrame
- 固定提交：6fe247eb09d8e154f0530305e8a2c572b58a3ec4
- 上游许可：MIT，完整原文保留在 LICENSE-CutFrame.txt。
- 未运行上游应用；未引入 yt-dlp、YouTube、Deno、Node 运行时探测或 imageio-ffmpeg。
- Flask、Werkzeug、Jinja2、MarkupSafe、itsdangerous、click 使用 BSD 许可；colorama 使用 BSD；blinker、zipp 使用 MIT；importlib_metadata 使用 Apache-2.0。实际安装版本锁定于 requirements.txt，各包许可文件保存在 .packages 的 dist-info 中。
- FFmpeg/FFprobe 为本机已有独立工具，其 LGPL/GPL 构建许可与应用依赖分开，不宣称其为 MIT/BSD。本目录不重新分发 FFmpeg，也不改变其许可。
- 当前使用本机字体显示与字幕渲染，不复制字体文件到项目包。
- 此工具仅监听本机回环地址，不是公网多租户服务。

- 新增本地 GPT-SoVITS 进程调用，使用机器已有安装，不打包分发其模型或运行时。代码许可 MIT，原文见 LICENSE-GPT-SoVITS.txt。模型与用户音色素材单独保留在本地私有目录；代码许可不代替音色素材的商用授权，正式商业分发仍需核对实际模型与音色素材许可。


## Chinese-CLIP ViT-B/16 本地候选检索

- 官方代码：https://github.com/OFA-Sys/Chinese-CLIP
- 官方权重：https://huggingface.co/OFA-Sys/chinese-clip-vit-base-patch16
- 官方仓库 MIT 原文：`LICENSE-Chinese-CLIP.txt`，保留版权声明。
- 固定权重修订与本地 SHA256：`../local/ai-models/chinese-clip/installation-manifest.json`。
- transformers 4.57.3（Apache-2.0）与 PyTorch 2.7.1+cu128（BSD 风格）沿用本机环境。
- 官方 HF 模型卡未单列许可证字段；代码仓库 MIT 与权重分发许可不应混为已完成的商用发行审计。本阶段为本地技术验证，正式封装分发前需要确认权重授权范围及全部依赖声明。
