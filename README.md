# Galgame 汉化 Skill

面向 Codex 的视觉小说汉化工作流，覆盖引擎识别、剧情文本、选项、图片按钮、中文编码与字体、闪退排查、稳定版备份和跨设备迁移。

随附的二进制脚本支持 NEKOPACK4A 和部分 NekoSDK ADVSCRIPT2 命令。其他引擎可使用通用流程，并根据实际格式接入相应工具。

## 安装与使用

将本仓库放入用户级 skills 目录下的 `galgame-localization` 文件夹，确保 `SKILL.md` 位于该文件夹第一层。当前 Codex 文档列出的用户级位置为 `~/.agents/skills`，项目级位置为 `.agents/skills`。[OpenAI 官方说明](https://learn.chatgpt.com/docs/build-skills)

```powershell
git clone https://github.com/ZZZZZZYX114514/galgame-localization-skill.git "$env:USERPROFILE/.agents/skills/galgame-localization"
```

在游戏工程目录发起任务。

```text
使用 $galgame-localization 继续这个游戏的汉化，先检查已有备份和当前进度，完成剧情选项并打包可迁移补丁。图片访问范围按我在本次任务中的要求执行。
```

Codex 可根据任务自动选用技能，也支持显式调用 `$galgame-localization`。安装后若尚未显示，可重启 Codex。[OpenAI 官方说明](https://learn.chatgpt.com/docs/build-skills)

## 随附工具

| 工具 | 功能 |
| --- | --- |
| `scripts/nekopack.py` | 列出、解包、重打包和验证 NEKOPACK4A |
| `scripts/nekosdk.py` | 解析并修改两种 ADVSCRIPT2 对白记录 |
| `scripts/text_pipeline.py` | 提取 UTF-8 JSONL，以源哈希校验后写回 GBK 译文 |
| `scripts/crop_bmp_region.py` | 只读取已确认纯文字矩形的 BMP 像素并导出 PNG |

归档和文本工具使用 Python 3.10 及以上版本的标准库。BMP 裁剪及其测试需要 Pillow。

```powershell
python -m pip install Pillow
python -m unittest discover -s tests -v
```

命令示例与格式边界见 [SKILL.md](SKILL.md) 和 `references/`。测试使用合成数据。

## 图片访问与发布范围

图片访问权限由当前用户要求决定。限制 CG 访问的任务通过索引、引用、尺寸和数值分析推进，纯文字预览需要先确认矩形位置。仓库发布内容包含通用工具、流程说明和合成测试。

## 验证范围

这些工具仍需在具体游戏版本上验证。ADVSCRIPT2 助手覆盖两种对白命令，选项和其他命令需要单独定位。脚本检查、运行验证和完整通关分别记录，译文质量需要人工复核。

## 许可

MIT，见 [LICENSE](LICENSE)。
