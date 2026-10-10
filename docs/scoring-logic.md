# 打分逻辑

这份文档说明推荐分数是怎么算出来的。它和代码必须保持一致：

- **规则版本**：见下面“当前参数”里的 `ruleset_version`，以及文末的修改记录。
- **每次修改打分逻辑或参数，都要同步更新这份文档。**单元测试会检查：这里的参数和 `config/scoring.yaml` 是否相同，这里列出的规则和否决是否与 `scorer/rules/` 下的代码一一对应，修改记录的最新版本是否等于当前版本。对不上，测试就不通过。
- 文档与代码不一致时，以这份文档为准，由 agent 把代码改成和文档一致。

## 你怎样干预打分

| 想做的事 | 改哪里 | 之后要做什么 |
| --- | --- | --- |
| 调数字：权重、门槛、阈值 | 同时改 `config/scoring.yaml` 和本文档“当前参数”一节，两处要一样 | 版本号加 1，运行 `python3 -m scorer.version --update`，在文末加一行修改记录 |
| 调某个钓点：最佳潮段、阵风和浪高上限、是否夜钓 | `config/spots.yaml` | 同上 |
| 改一条规则的算法，或新增、删除规则 | 直接改本文档里对应小节的文字，写清楚你想要的算法 | 把文档交给 agent，由它按文档改 `scorer/rules/` 下的代码和测试，并完成版本号和修改记录 |

改完数字不需要找 agent，推送后下一次采集就会生效。改算法需要 agent 落实到代码，但你只要改这份文档，不用看代码。

## 计算流程

对每个钓点的每个小时：

1. **逐条运行规则**。每条规则给出一个 0 到 1 的得分和一句理由。规则缺少它需要的数据或钓点设置时，这条规则在这个小时被跳过。
2. **加权平均**。小时分数 = 各条未被跳过的规则的得分按权重加权平均，再乘以 100，保留一位小数。被跳过的规则不参与，它的权重由其余规则分摊。
3. **安全否决**。任何一条否决成立，这个小时的分数直接记为 0，并附上安全提示。
4. **合并成推荐时段**。连续的、未被否决且分数不低于 `min_score` 的小时合并成一个时段；时段至少 `min_hours` 个小时。时段分数是其中各小时分数的平均，保留一位小数。时段按分数从高到低排列。
5. **可信度**。时段的开始时间距采集时间不超过 `high_confidence_hours` 小时，可信度为 `high`，否则为 `low`。

每个时段附带每条规则的理由：得分是该规则在时段内各小时得分的平均，文字取自时段内分数最高的那个小时。

## 当前参数

下面这段必须和 `config/scoring.yaml` 的内容相同。

<!-- scoring.yaml:start -->
```yaml
ruleset_version: 3

# How much each rule counts. Only the proportions matter.
# A rule that is skipped for an hour (missing data or missing spot setting)
# drops out and the others share its weight.
weights:
  tide: 3
  wind: 3
  wave: 2
  rain: 1
  light: 1

# Hours scoring at least min_score are joined into recommended windows.
window:
  min_score: 60          # 0-100
  min_hours: 2           # shortest window; data is hourly, so 2 hours covers the 1.5 h minimum
  high_confidence_hours: 72   # windows starting later than this are marked "low" confidence

# Settings of the individual rules.
rules:
  tide:
    falloff_min: 120     # outside the spot's best window the score falls to 0 over this many minutes
  wind:
    calm_kmh: 10         # at or below this wind speed the score is full
    strong_kmh: 35       # at or above this wind speed the score is 0
    offshore_bonus: 0.15
    onshore_penalty: 0.15
  light:
    window_min: 60       # minutes either side of sunrise and sunset that score 1.0
    day_score: 0.5       # the rest of the day
    night_score: 0.0
```
<!-- scoring.yaml:end -->

## 规则

### 规则 `tide`（潮汐）

- 意图：离高潮越近越好，落在钓点的最佳潮段内得满分。
- 输入：这个小时距最近一次高潮的分钟数（高潮前为负，高潮后为正）；钓点的 `best_tide_window_min`，例如 `[-120, 120]`。
- 算法：在最佳潮段内得 1。超出潮段时，每超出 1 分钟扣 `1 / falloff_min`，扣到 0 为止。
- 例子：潮段 `[-120, 120]`、`falloff_min` 为 120 时，高潮后 3 小时（超出 60 分钟）得 0.5，高潮后 4 小时得 0。
- 跳过：钓点没有设置最佳潮段，或没有潮汐数据。

### 规则 `wind`（风）

- 意图：风越小越好；离岸风加一点分，向岸风减一点分。
- 输入：风速；风相对岸线的方向（离岸、向岸、侧风，由钓点的 `shore_facing_deg` 算出）。
- 算法：风速不超过 `calm_kmh` 得 1，达到 `strong_kmh` 得 0，中间按直线变化。然后离岸风加 `offshore_bonus`，向岸风减 `onshore_penalty`，侧风不加不减。结果限制在 0 到 1 之间。
- 钓点没有设置岸线朝向时：只按风速计分，方向不加不减，理由里注明方向未计分。
- 跳过：没有风速数据。

### 规则 `wave`（浪）

- 意图：浪越低越好，以钓点的上限为尺度。
- 输入：浪高；钓点的 `max_wave_m`。
- 算法：得分 = 1 − 浪高 ÷ 上限，限制在 0 到 1 之间。
- 例子：上限 2.0 米时，浪高 0.5 米得 0.75。
- 跳过：没有浪高数据，或钓点没有设置上限。

### 规则 `rain`（降雨）

- 意图：降雨概率越低越好。
- 输入：降雨概率（百分比）。
- 算法：得分 = 1 − 降雨概率 ÷ 100。
- 跳过：没有降雨概率数据。

### 规则 `light`（天光）

- 意图：日出和日落前后是最好的时段。
- 输入：这个小时的开始时刻；当天的日出、日落时间；`is_daylight`。
- 算法：距日出或日落不超过 `window_min` 分钟得 1；其余白天得 `day_score`；夜间得 `night_score`。
- 跳过：不会被跳过。

## 安全否决

否决只看是否超过上限，刚好等于上限不否决。

### 否决 `gust`（阵风）

阵风大于钓点的 `max_gust_kmh` 时否决。没有阵风数据或钓点没有设置上限时，这条否决不起作用。

### 否决 `wave`（浪高）

浪高大于钓点的 `max_wave_m` 时否决。没有浪高数据或钓点没有设置上限时，这条否决不起作用。

### 否决 `night`（夜间）

这个小时不是白天（`is_daylight` 为 false），并且钓点的 `allow_night` 不是 true 时否决。`is_daylight` 的范围是日出前 60 分钟到日落后 60 分钟，所以日出前、日落后各一小时不算夜间。

## 数据缺失时

某个小时缺少预报数据时，用到这些数据的规则被跳过，其余规则照常计分；对应的安全否决也不起作用。这意味着一个没有风和浪预报的小时，会只按潮汐和天光打分，并且没有经过阵风和浪高上限的检查。这是 Liang 在 2026-10-10 的决定。

## 修改记录

每次修改加一行，最新的在最下面。

| 版本 | 日期 | 改了什么 | 原因 |
| --- | --- | --- | --- |
| 1 | 2026-10-10 | 初版：五条规则、三条阵风、浪高、夜间否决，外加一条“没有阵风或浪高预报时不推荐”的否决 | M2 首次实现 |
| 2 | 2026-10-10 | 去掉“没有阵风或浪高预报时不推荐”的否决 | Liang 决定不保留 |
| 3 | 2026-10-10 | 只改了风规则的一句理由文字：钓点没有岸线朝向时，不再显示配置项名称 `shore_facing_deg`，改成普通的英文说明。分数的算法没有变 | 这句话会显示在网页上，原来的写法访客看不懂 |
