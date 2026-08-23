# ptcgp-deck2qr 产品需求文档

状态：Draft  
版本：0.1  
日期：2026-08-16

## 1. 项目概述

`ptcgp-deck2qr` 最终目标是将 Pokémon TCG Pocket 卡组截图转换为游戏可扫描导入的 QR Code。

项目分为两个相互独立的阶段：

```text
阶段一（识别与标准化）
卡组截图
  ↓
卡牌检测、识别和数量解析
  ↓
标准卡组文本 deck.txt

阶段二（本地 GUI 已接入）
标准卡组文本 deck.txt
  ↓
格式解析、Card ID 映射和 Deck Code 编码
  ↓
可由游戏扫描的 QR Code
```

当前本地 GUI 在阶段一识别完全通过后继续执行阶段二。标准卡组文本仍是两个阶段之间的稳定边界；二维码不得直接消费截图识别内部数据。

## 2. 背景与问题

用户分享的卡组截图来源和布局差异很大，目前至少包括：

1. 游戏内完整卡牌网格，重复卡分别出现。
2. 网站生成的插画缩略图列表，卡牌数量写在独立的 `Quantity` 区域。
3. 攻略网页的完整卡图列表，数量显示为 `×2`、`×1`。
4. 卡组拼图，数量显示在卡牌右下角的数字徽章中。

这些截图在以下方面不一致：

- 卡图可能是完整卡牌，也可能只有插画区域。
- 重复卡可能重复展示，也可能只展示一次并附带数量。
- 数量可能位于卡牌下方、文字中或角标内。
- 网格列数、间距、背景和分辨率不同。
- 卡牌语言可能不同。

因此，第一版不能依赖单一固定坐标，也不能把 QR 编码逻辑和图片识别逻辑绑在一起。

## 3. 产品目标

当前 Demo 的目标是：

> 输入一张完整卡组截图和用户指定的能量类型，自动识别卡组，输出符合 Deck Text Format v1 的 `deck.txt`，并在识别完整通过后由本地 GUI 自动生成卡组二维码。

示例命令：

```bash
ptcgp-deck2qr recognize deck.png --energy lightning
```

预期输出：

```text
output/
├── deck.txt
├── recognition.json
└── recognized.png
```

本地 GUI 还会在浏览器内显示二维码，并提供 PNG 下载和 Deck Code 复制；二维码不是 CLI
识别命令写入 `output/` 的固定文件。

其中：

- `deck.txt`：标准化卡组文本，是 Demo 的主要结果。
- `recognition.json`：识别过程、候选项、置信度和数据库映射，用于调试。
- `recognized.png`：在原图上标记检测区域、识别结果和数量。

## 4. 非目标

当前 Demo 不实现：

- QR Code 解码。
- 云端托管的 GUI 或 Web 服务。
- 云端服务和用户系统。
- 任意实拍、倾斜或严重透视的实体卡牌照片。
- 用户收藏统计。
- 自动推断能量类型。
- 自动修改低置信度结果。
- 为所有网站分别编写专用爬虫。

## 5. 标准卡组文本格式

规范性定义见 [`docs/deck-text-format-v1.md`](docs/deck-text-format-v1.md)。本节保留产品层摘要；若两者出现实现细节差异，以独立格式规范为准，并应同步修正文档。

### 5.1 设计目标

Deck Text Format v1 必须满足：

- 人可以直接阅读和修改。
- Git diff 友好。
- 不依赖字段顺序模糊解析。
- 卡名可以包含空格、连字符和撇号。
- 能表达 Pokémon、Trainer、数量和能量。
- 能被后续 QR 模块稳定解析。
- 不把识别置信度等调试信息混入卡组正文。

### 5.2 文件格式

文件使用 UTF-8，扩展名为 `.txt`。

规范示例：

```text
# PTCGP-DECK 1
name: miraizone - ori
energy: lightning

[pokemon]
2 Magnemite | A1-097
2 Magneton | A1-098
2 Magnezone | A1-099
1 Miraidon ex | B3a-019
2 Oricorio | B3a-020

[trainer]
2 Poké Ball | PROMO-A-005
2 Professor's Research | PROMO-A-007
1 Cyrus | A2-150
```

### 5.3 语法规则

文件头：

```text
# PTCGP-DECK 1
```

这是必填项，用于识别格式和版本。

元数据：

```text
name: <deck name>
energy: <energy>[, <energy>...]
```

- `name` 可选；无法从截图可靠识别时使用输入文件名。
- `energy` 在当前 Demo 中由用户参数提供。
- 允许 1–3 种能量。
- 顺序必须保留，供 QR 编码使用。
- 第一版正常接受：`grass`、`fire`、`water`、`lightning`、`psychic`、`fighting`、`darkness`、`metal`。

卡牌分区：

```text
[pokemon]
[trainer]
```

卡牌行：

```text
<count> <name> | <set>-<number>
```

规则：

- `count` 为正整数，正常 PTCGP 卡组中为 1 或 2。
- `name` 为展示字段，不作为唯一身份。
- `|` 是强制分隔符，避免卡名中的空格造成解析歧义。
- `set` 使用 `ptcgp-database` 中的 set code，例如 `A1`、`B3a`、`PROMO-A`。
- `number` 输出为至少三位，例如 `001`、`097`、`150`。
- 身份主键是 `(set, number)`。

### 5.4 标准化规则

输出必须：

1. 将相同 `(set, number)` 的重复识别结果聚合为一行。
2. `[pokemon]` 和 `[trainer]` 内分别排序。
3. 使用数据库中的标准英文名作为 `name`。
4. 保留用户提供的 energy 顺序。
5. 确保所有卡牌 `count` 之和为 20。
6. 使用 LF 换行并以一个换行符结束文件。

建议排序键：

```text
entity type → set release order → set code → card number
```

### 5.5 相同图片对应多个 print ID

本地数据库中存在同一图片对应多个 `(set, number)` 的情况，单凭截图不能区分这些数据库别名。

处理规则：

- 识别器必须先确定 visual asset 和游戏 semantic entity。
- 若 visual asset 对应多个 print ID，`recognition.json` 必须记录所有候选。
- `deck.txt` 使用确定性的 canonical print：优先发布时间最早的 set，其次按 set code 和 number 排序。
- `recognized.png` 使用黄色标记，并显示 `print alias`。
- 不能将 canonical print 描述成“从图片中唯一识别出的版本”。

该选择不会影响后续 QR，因为这些 print alias 使用同一个游戏实体 ID。

## 6. 输入需求

### 6.1 图片输入

Demo 接受：

- PNG。
- JPEG。
- WebP（如果 Pillow/OpenCV 运行环境支持）。

限制：

- 一张图片必须描述一副完整卡组。
- 卡牌区域不能被聊天浮层或水印大面积遮挡。
- 图片中必须能够得到卡牌图像或主要插画区域。
- 不支持视频和动图。

### 6.2 能量输入

能量由用户显式指定，不从卡组内容推断。

示例：

```bash
ptcgp-deck2qr recognize deck.png --energy lightning
ptcgp-deck2qr recognize deck.png --energy grass,fire
ptcgp-deck2qr recognize deck.png --energy psychic,fighting,darkness
```

校验规则：

- 至少一种，最多三种。
- 不允许重复。
- 不允许未知值。
- 当前 Demo 不接受正常编辑器无法选择的 Dragon 和 Colorless 能量。

### 6.3 数据库输入

默认从外部路径读取本地 `ptcgp-database`：

```text
H:\CodexCode\ptcgp-database\dist
```

CLI 应允许覆盖：

```bash
--database-path <path-to-dist>
```

Demo 不复制或维护第二份 `cards.json`，只生成可重建的识别索引。

## 7. 需要支持的截图风格

### Style A：独立完整卡牌网格

特征：

- 每份卡牌实例分别出现。
- 两张相同卡会出现两次。
- 不需要读取数量文字。
- 卡牌通常为完整竖版卡图。

数量规则：每个检测到的卡牌实例贡献 `1`，识别后按身份聚合。

### Style B：插画缩略图 + Quantity

特征：

- 只显示卡牌插画，不显示完整卡框。
- 卡名位于插画上方。
- 数量位于插画下方的 `Quantity` 区域。
- 每种卡只显示一次。

识别策略：使用数据库卡图的 artwork ROI 索引匹配缩略图；数量只对相邻数量区域进行数字 OCR。

### Style C：完整卡图 + `×N` 文本

特征：

- 每种卡显示一次。
- 卡牌下方显示名称与 `×1` / `×2`。
- 网页边框、放大镜按钮等可能紧邻卡图。

识别策略：检测完整卡牌区域；数量对卡牌下方的局部文本区域进行数字 OCR或 `×1`/`×2` 模板识别。

### Style D：完整卡图 + 数字徽章

特征：

- 卡牌排列紧密。
- 右下角徽章部分遮挡卡牌。
- 徽章数字表示数量。
- 每种卡只显示一次。

识别策略：匹配时忽略卡牌右下角区域；数量通过徽章区域的数字识别获得。

### 风格选择

默认使用：

```text
--style auto
```

Demo 可提供诊断用覆盖参数：

```text
--style separate-cards
--style quantity-label
--style count-text
--style count-badge
```

`auto` 识别失败时应要求用户指定 style，而不是猜测后继续输出错误卡组。

## 8. 识别流程

```text
读取图片
  ↓
检测候选卡牌/插画矩形
  ↓
根据候选长宽比、网格和数量区域判断截图风格
  ↓
裁切并归一化 visual region
  ↓
感知哈希召回 top-k
  ↓
OpenCV 二次匹配
  ↓
确定 visual asset / semantic entity
  ↓
按截图风格解析数量
  ↓
聚合卡牌
  ↓
验证总数为 20
  ↓
输出 Deck Text Format v1
```

## 9. 卡牌检测需求

最小 Demo 使用经典图像处理，不引入目标检测模型。

候选检测应组合：

- 边缘和轮廓检测。
- 矩形长宽比过滤。
- 规则网格聚类。
- 相近尺寸聚类。
- 背景/卡牌边界对比。

需要支持两类候选区域：

1. 完整卡牌：竖版，接近标准卡牌长宽比。
2. artwork thumbnail：横版或接近横版，只包含插画。

检测结果必须保留：

```text
bbox
detection score
row / column
detected style
crop quality
```

## 10. 卡牌匹配需求

### 10.1 索引来源

直接读取：

```text
cards.json
images/cards-by-set/{set}/{number}.webp
```

索引以唯一 `image` 文件为单位，避免对数据库中的重复图片重复计算。

### 10.2 索引内容

每个 visual asset 至少生成：

- 完整卡牌 pHash。
- artwork ROI pHash。
- artwork ROI RGB/color hash。
- dHash。
- 简化颜色直方图。

可选二次特征：

- ORB descriptors。
- 边缘图。

### 10.3 匹配策略

1. 通过 hash 对所有 visual assets 召回 top 10。
2. 对 top 10 使用 normalized correlation、边缘相似度和颜色差异重新排序。
3. 必要时使用 ORB 对相近候选做第三次判断。
4. 输出最佳 visual、最佳 entity，以及最佳候选与次佳不同 entity 的 margin。

### 10.4 语言处理

Demo 不做卡名 OCR，也不依赖截图中的卡名作为主识别方式。

语言差异通过优先匹配 artwork ROI 规避。完整卡图匹配时应降低文字区域权重。

## 11. 数量识别需求

数量解析只需要识别 `1` 和 `2`，不做通用 OCR。

优先级：

1. Style A：实例计数，不 OCR。
2. Style D：徽章数字模板/数字 OCR。
3. Style C：局部 `×1` / `×2` 模板识别。
4. Style B：局部 Quantity 数字识别。

不得对整张图片运行不受约束的 OCR。每次 OCR 必须限制在已经与某张卡绑定的局部 count ROI，并将字符集限制为：

```text
1 2
```

数量无法可靠识别时，该卡状态为 `ambiguous-count`，整个 deck 不得被标记为成功。

## 12. Card Database 映射

数据库字段映射：

```text
print key    = (set, number)
visual id    = image filename
entity type  = cPK → pokemon, cTR → trainer
entity id    = image filename 中的六位数字
```

`cards.extra.json` 不作为必需依赖，因为其新系列覆盖不完整。

索引构建时必须验证：

- `(set, number)` 唯一。
- 对应图片存在。
- `image` 能解析出 PK/TR 和 entity ID。
- 同一 visual 对应的多个 print ID 必须映射到同一 entity。

## 13. 输出需求

### 13.1 deck.txt

必须符合 Deck Text Format v1，并满足：

- 总卡牌数量为 20。
- 至少有一个 Pokémon 分区条目。
- 每张卡有有效的 set 和 number。
- 能量来自用户参数。

### 13.2 recognition.json

建议结构：

```json
{
  "schema_version": 1,
  "input": "deck.png",
  "detected_style": "count-badge",
  "database": {
    "source": "pokemon-tcg-pocket-database",
    "cards_sha256": "..."
  },
  "energy": ["fighting"],
  "cards": [
    {
      "bbox": [61, 40, 344, 420],
      "count": 2,
      "decision": "accepted",
      "visual_id": "cPK_...webp",
      "entity_type": "pokemon",
      "entity_id": 1234,
      "selected_print": "A1-001",
      "print_candidates": ["A1-001"],
      "visual_score": 0.98,
      "entity_margin": 0.14,
      "top_candidates": []
    }
  ],
  "validation": {
    "card_count": 20,
    "accepted": true
  }
}
```

### 13.3 recognized.png

标注颜色：

- 绿色：卡牌和数量均可靠。
- 黄色：entity 可靠，但 print 存在 alias。
- 橙色：数量不可靠。
- 红色：卡牌 entity 不可靠。

标签建议：

```text
01 A1-001 ×2  entity=PK:10  98.4%
```

## 14. 成功与失败策略

Demo 只有在以下条件全部满足时返回成功：

- 找到至少一个合理的 screenshot style。
- 所有卡牌 entity 均达到自动接受阈值。
- 所有数量均确定。
- 聚合数量等于 20。
- 每个输出 print ID 都能在数据库中解析。
- energy 参数有效。

失败时仍应生成 `recognition.json` 和 `recognized.png`，但不生成正式 `deck.txt`；可生成 `deck.partial.txt` 供人工检查。

建议错误码：

```text
STYLE_UNSUPPORTED
CARD_REGION_NOT_FOUND
MATCH_AMBIGUOUS_ENTITY
COUNT_AMBIGUOUS
CARD_TOTAL_NOT_20
DATABASE_MAPPING_FAILED
ENERGY_INVALID
```

## 15. CLI 需求

核心命令：

```bash
ptcgp-deck2qr recognize <image>
  --energy <energy[,energy...]>
  [--style auto]
  [--database-path <path>]
  [--output <directory>]
  [--debug]
```

索引命令：

```bash
ptcgp-deck2qr build-index
  [--database-path <path>]
  [--output <index path>]
```

退出码：

```text
0  成功生成 deck.txt
1  输入或参数错误
2  图片/风格检测失败
3  卡牌或数量存在歧义
4  卡组校验失败
5  数据库或索引错误
```

### 15.1 可选本地 GUI

Demo 可以提供 `ptcgp-deck2qr gui` 作为 CLI 的本地操作界面。GUI 只覆盖当前已有能力：

- 选择一张截图。
- 显式选择 1–3 种能量。
- 可选覆盖截图样式。
- 启动识别并查看原图、标注图和失败原因。
- 复制或下载成功的 `deck.txt`，或查看失败诊断。

GUI 不增加卡组历史、收藏、商店、社区、账号、云端同步或卡牌编辑功能。
识别通过后，GUI 自动从已验证 Deck 生成 Deck Code 和二维码。若结构和数量证据可靠、每个
位置都有数据库候选，但仅识别到 18–19 张或存在实体歧义，GUI 可以生成明确标注的草稿
二维码供用户尝试导入和编辑；该结果仍为识别失败，不生成正式 `deck.txt`。其他失败不得生成。
它必须调用同一 Python 识别管线，不得在前端复制识别和验证规则。

## 16. 技术方案约束

推荐运行依赖：

```text
Python 3.11+
numpy
Pillow
opencv-python-headless
ptcgp-deckcode（React 构建时固定版本，运行时不联网）
```

如果局部数字识别需要 Tesseract，必须作为可选依赖；优先实现只支持 `1`、`2` 的模板识别，避免给 Demo 增加系统级 OCR 安装要求。

当前阶段不引入：

```text
PyTorch
Ultralytics
TensorFlow
ONNX Runtime
CLIP
向量数据库
```

## 17. 推荐模块边界

```text
src/ptcgp_deck2qr/
  cli.py
  pipeline.py

  decktext/
    model.py
    parser.py
    writer.py
    validation.py

  carddb/
    loader.py
    identities.py

  detection/
    regions.py
    styles.py
    counts.py

  matching/
    index.py
    fingerprints.py
    matcher.py

  debug/
    annotate.py
    report.py
```

`decktext` 必须独立于图片识别。QR 模块只能依赖 Deck model 和 `carddb`，正常路径必须消费
已验证的 20 张 Deck；显式草稿路径仅接受结构可靠的 18–20 张 Deck。QR 模块不能依赖 OpenCV
或截图对象。

当前 QR 阶段的边界：

```text
deck.txt
  ↓ decktext.parser
Deck model
  ↓ qr.encoder
Deck Code
  ↓ qr.renderer
deck-qr.png
```

## 18. Demo 验收标准

以用户提供的四张样本为首批验收集：

1. 能正确区分或接受覆盖四种截图风格。
2. 每张图都能识别出正确的卡牌 semantic entity。
3. 正确解析重复实例、Quantity、`×N` 和数字徽章四种数量表达。
4. 每张图聚合后的数量都等于 20。
5. 能量严格采用 CLI 参数，不进行推断。
6. 输出的 `deck.txt` 能被独立 parser 无损读回。
7. writer 执行两次得到完全相同的文本。
8. 任何低置信度 entity 都不能被静默写入成功结果。
9. `recognized.png` 能清楚定位检测、匹配或数量错误。

准确率目标：

```text
首批四张样本：entity 识别 100%
首批四张样本：数量识别 100%
自动接受结果：不允许已知误识别
```

由于测试集很小，这些指标只代表 Demo 通过，不代表对任意互联网截图的泛化准确率。

## 19. 开发顺序

### Milestone 0：格式先行

- 完成 Deck Text Format v1 定义。
- 实现独立 model、parser、writer 和 validation。
- 使用手工卡组文本验证 round-trip。

### Milestone 1：数据库与索引

- 读取本地 `ptcgp-database`。
- 建立 print、visual、entity 三层映射。
- 对唯一 visual asset 构建多 ROI fingerprint index。

### Milestone 2：完整卡图识别

- 支持 Style A。
- 支持 Style D 的完整卡图识别，暂不处理徽章。

### Milestone 3：数量系统

- 实例计数。
- 数字徽章 `1`/`2`。
- `×1`/`×2`。
- Quantity 数字。

### Milestone 4：artwork-only 识别

- 建立 artwork ROI index。
- 支持 Style B。

### Milestone 5：整合与调试输出

- 自动 style 判断。
- 生成 `deck.txt`、`recognition.json`、`recognized.png`。
- 对四张样本做回归测试。

### Milestone 6：QR

- 已独立实现 `validated Deck → QR input → Deck Code → QR`。
- 已实现显式标记的 `18–20 card review draft → QR`，但 18–19 张需真机确认游戏是否接受。
- 已用编码后再解析的 round-trip 测试验证 payload 结构。
- 待增加真机扫描验收。

## 20. 开放问题

实现前仍需通过小实验确认：

1. Style B 的插画缩略图是否与本地卡图 artwork ROI 使用相同裁切比例。
2. 不同 Pokémon、Item、Supporter 的 artwork ROI 是否需要分别配置。
3. Style C 的网页是否总把数量放在卡牌正下方。
4. Style D 的徽章颜色和形状是否固定，还是不同网站会变化。
5. 自动 style 判断的可靠性是否足以默认启用；如果不足，应要求用户显式指定 style。
6. canonical print alias 是否需要在 `deck.txt` 中增加可选注释，还是只保留在 `recognition.json`。

## 21. 最终决策

当前阶段的产品边界确定为：

```text
输入：一张卡组截图 + 用户指定能量
输出：标准 deck.txt + 可验证的识别调试结果 + 通过本地 GUI 自动生成的 QR Code
```

正式 QR Code 只在当前 Demo 的识别结果完整通过后生成。对于仅缺 1–2 张或仅有实体歧义、
且结构和数量证据可靠的结果，可以生成明确标注的草稿 QR 供用户尝试导入后编辑；草稿不计为
识别通过。QR 模块只消费 Deck model 和数据库映射，从而避免 QR 协议变化反向污染图片识别模块。
