---
name: galgame-localization
description: Use when localizing a locally available Galgame or visual novel into Chinese, completing untranslated choices or image buttons, diagnosing a rebuilt game's crash, or packaging a localization patch. Includes format-specific NEKOPACK4A and NekoSDK ADVSCRIPT2 helpers.
---

# Galgame 汉化

将可运行原版逐步变成可验证、可恢复、可迁移的汉化版本。根据实际文件头选择引擎工具，每个发布版本记录修改范围和运行证据。

## 接续已有工程

先读已有提取表、构建脚本、备份清单和最近的测试记录。保留用户已确认可运行的版本，并记录本轮要补的内容。用户只要求选项、内容或迁移时，直接沿用已确认的范围。

内置文本工具以 CP932 原版快照作为输入。续译时将新增译文合并到已完成译文表，使用同一原版快照与全部已完成记录重建，再比较上版译文是否保留。

用文件名、文件头、归档索引和脚本字符串识别资源。记录程序版本与原文件 SHA-256、脚本编码、字体路径、资源包以及存档实际位置。首次写回前保存要修改的原文件，后续备份使用独立版本目录。

**用户限制图片访问时，将限制写入当前任务记录。** 如禁止读取 H CG，使用索引、尺寸字段、脚本引用和数值验证。缩略图、联系表、整屏截图和含 CG 示例的设置面板也可能显示这些内容。只有从元数据或已知布局确认矩形区域纯为文字后，才读取该矩形的像素。位置不明时继续处理可定位的脚本与资源。

## 选择操作入口

| 当前工作 | 参考与工具 |
| --- | --- |
| NEKOPACK4A 索引、重打包、启动崩溃 | 阅读 [NekoSDK 格式](references/nekosdk.md)，用 `python scripts/nekopack.py list` 查看索引 |
| ADVSCRIPT2 对白提取与写回 | `python scripts/text_pipeline.py extract` 与 `apply` |
| 选项、按钮、字体和控制码 | 阅读 [文本与界面](references/text-and-ui.md) |
| 纯文字 BMP 区域预览 | `python scripts/crop_bmp_region.py`，先确认矩形及像素格式 |
| 闪退、稳定版备份、补丁迁移、存档迁移 | 阅读 [验证与交付](references/verification-and-delivery.md) |

其余引擎沿用其原生脚本格式和已验证工具。内置二进制工具仅适用于下面参考中说明的格式变体，先用小样本验证。

## 文本工作循环

1. 用归档条目名、脚本标记和分支引用建立提取范围。每条译文保留文件名、记录位置、原文、人物名、原脚本哈希和译文。
2. 先验证少量旁白、人物对白及分支选项。选项单独统计，并检查显示文字到分支目标的对应关系。
3. 译文沿用术语表与人物称呼，保留命令、占位符、换行规则和控制序列。分批翻译后检查漏译、乱码、编码失败、异常长度及选项一致性。
4. 将译文写入独立构建产物。按字节更新长度字段与偏移，逐项核对选中条目，逐字节比较其余压缩条目。
5. 在获准的验证范围内启动实际游戏，验证中文渲染、选项跳转、存读档和本轮涉及的界面。把实际执行的检查与仍待检查的内容记入交付清单。

调用示例中的相对路径以 skill 目录为基准。

```powershell
python scripts/nekopack.py list "C:/game/gamedata/scr.pak"
python scripts/text_pipeline.py extract "C:/game/gamedata/scr.pak" "C:/work/units.jsonl"
# 在 units.jsonl 中填写 translation 与可选 translation_name。
# 将全部已完成记录汇总到 completed.jsonl，保留先前批次的译文。
python scripts/text_pipeline.py apply "C:/game/gamedata/scr.pak" "C:/work/completed.jsonl" "C:/work/staged-scr.pak"
```

提取报告中的 warnings 计入覆盖范围，逐项定位失败原因。内置提取器识别两种对白命令，选项和其他引擎命令需要根据当前样本另行定位。

## 发布前检查

对照用户要求列出内容、选项、按钮和其他界面的完成情况。机器翻译、抽样验证、目标设备尚待实测等情况按实际写明。

补丁附版本、目标路径、原版及译版哈希、安装步骤和恢复方式。存档按用户要求单独收录，记录覆盖现有设置或进度的影响。公开发布技能时，选用工具源码、文档和合成夹具，并核对发布文件清单。
