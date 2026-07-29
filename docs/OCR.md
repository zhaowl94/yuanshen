# OCR 指南

## 支持边界

v1 正式支持：

- 简体中文游戏界面；
- 单张、已裁剪的圣遗物详情卡片；
- 五星圣遗物；
- 清晰显示部位、主词条、等级和三至四个副词条的图片。

现有历史样例约为 293–448 像素宽的裁剪卡片。v1 不承诺从整屏截图自动定位面板。

## 安装

EasyOCR 和 PyTorch 不是核心评分依赖。Windows 用户应先使用 PyTorch 官方选择器安装
与 CPU 或 CUDA 匹配的包，然后：

```powershell
uv sync --extra ocr
uv run yuanshen-score models install easyocr-zh
uv run yuanshen-score models verify easyocr-zh
```

模型默认保存在 `.yuanshen-score/models`，该目录不会进入 Git。安装清单记录引擎
版本、语言、文件大小和 SHA-256；评分过程禁止静默下载缺失模型。

## 识别与人工修正

```powershell
uv run yuanshen-score ocr card.png -o output\card.json
```

默认最低置信度是 `0.65`。关键字段低于阈值时，该项停止评分。推荐打开输出 JSON
人工修正后运行 `score` 或 `simulate`。

解析器只对历史样例中已验证的少量、确定性中文误识别应用固定纠正，并在输出
`warnings` 中逐项记录原文和纠正结果。等级之后任何形似“名称+数值”却无法解析的
文字都会使该项失败，不会通过少算一个副词条来静默继续。

只有明确接受风险时才使用：

```powershell
uv run yuanshen-score ocr card.png --accept-low-confidence
```

完整原始 OCR token 可能包含无关文字或账号信息，因此默认不保存。仅本地调试时使用
`--debug-ocr local-debug.json`，并且不要提交该文件。

## 隐私

- 图片和识别结果不会上传；
- 普通日志不记录完整绝对路径或无关 OCR 文本；
- 真实截图应放在 Git 忽略目录；
- 自动化测试使用合成文字图与固定 token，不使用真实游戏素材；
- 批量清单以输入哈希跟踪结果。
