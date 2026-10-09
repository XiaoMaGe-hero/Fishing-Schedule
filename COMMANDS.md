# COMMANDS.md — 命令记录

开发过程中用过并且有效的命令都记在这里，Liang 可以照着自己运行和调试。记录规则见 `AGENTS.md` 第 4 节。

不要在这里写任何密钥，用环境变量名占位。

## 条目格式

```
### <用途，一句话>
- 命令：`<可直接复制的命令>`
- 运行目录：<相对项目根目录的路径>
- 前置条件：<依赖、环境变量；没有就写“无”>
- 预期结果：<看到什么算正常>
- 记录：<日期>，<里程碑>
```

## 1. 环境准备

### 确认 Python 版本
- 命令：`python3 --version`
- 运行目录：任意
- 前置条件：无
- 预期结果：显示 3.10 或更高。M0 的冒烟脚本只用标准库；M1 起的采集和发布代码需要 3.10 以上并安装依赖（见下一条）。
- 记录：2026-10-08，M0；2026-10-09 更新

### 安装依赖
- 命令：`python3 -m pip install -r requirements.txt`
- 运行目录：项目根目录
- 前置条件：Python 3.10+
- 预期结果：装好 jsonschema、PyYAML、astral、pytest，最后一行是 `Successfully installed ...` 或 `Requirement already satisfied`。
- 记录：2026-10-09，M1。在开发环境（Python 3.13）运行过；Liang 的 Mac 上还没运行过。

## 2. 数据源冒烟测试（tests/smoke）

本节的命令在 2026-10-08 都由 Liang 实际运行过：`run_all.py` 在 Mac 上（Python 3.12.12）四个数据源全部通过，ECan 在 GitHub Actions 上也通过。

### 运行全部四个数据源的冒烟测试
- 命令：`python3 tests/smoke/run_all.py`
- 运行目录：项目根目录 `FishingSchedule/`
- 前置条件：Python 3.9+，能访问外网
- 预期结果：依次打印 linz、weather、marine、ecan 的输出，最后的 SUMMARY 里四行都是 `RESULT: PASS`。每个脚本的输出保存在 `tests/smoke/output/<名称>-local.txt`，原始返回保存在 `tests/smoke/samples/`。共发出 5 到 6 个请求。
- 记录：2026-10-08，M0

### 只运行某一个数据源
- 命令：`python3 tests/smoke/run_all.py ecan`
- 运行目录：项目根目录
- 前置条件：同上。可选名称：`linz`、`weather`、`marine`、`ecan`，可以写多个。
- 预期结果：只运行指定的数据源，输出和保存位置同上。
- 记录：2026-10-08，M0

### 把 ECan 冒烟测试的工作流文件放到 GitHub 要求的位置
- 命令：`mkdir -p .github/workflows && cp tests/smoke/github-workflow-smoke-ecan.yml .github/workflows/smoke-ecan.yml`
- 运行目录：项目根目录
- 前置条件：无。只需做一次。开发工具不能直接写 `.github/workflows/`，所以要手动复制。
- 预期结果：出现 `.github/workflows/smoke-ecan.yml`，没有任何输出。
- 记录：2026-10-08，M0

### 在 GitHub Actions 上运行 ECan 冒烟测试
- 命令：在 GitHub 网页上操作：仓库 → Actions → “M0 smoke - ECan” → Run workflow。装了 `gh` 的话也可以用 `gh workflow run smoke-ecan.yml`。
- 运行目录：项目根目录（用 `gh` 时）
- 前置条件：工作流文件已复制到 `.github/workflows/`（见上一条），代码已推送到 GitHub 仓库
- 预期结果：任务结束后，在该次运行页面底部下载 `smoke-output`，里面的 `ecan-github.txt` 最后一行是 `RESULT: PASS` 或 `RESULT: FAIL`，说明 ECan 是否接受来自 GitHub Actions 的请求。
- 记录：2026-10-08，M0

## 3. 采集（collector）

### 在本机运行一次采集
- 命令：`python3 -m collector.run --out out`
- 运行目录：项目根目录
- 前置条件：已安装依赖；能访问外网
- 预期结果：四行 `[ok]`，最后一行 `wrote out/ - 4 of 4 sources ok`。生成 `out/conditions/new-brighton-pier.json`、`out/conditions/southshore.json`、`out/river_flow.json`、`out/meta.json`，以及 `out/state/` 下各数据源最近一次成功的结果。`out/` 不会被提交。
- 记录：2026-10-09，M1。开发环境访问不到数据源，只验证了“三个来源失败、LINZ 成功、照常产出文件”；四个来源全部成功的情况还没有实际运行过。

### 人为让一个数据源失败（验收用）
- 命令：`FISHING_FORCE_FAIL=ecan_flow python3 -m collector.run --out out`
- 运行目录：项目根目录
- 前置条件：先正常运行过一次，这样 `out/state/` 里有上次的数据。可选名称：`linz_tides`、`open_meteo_forecast`、`open_meteo_marine`、`ecan_flow`。
- 预期结果：该来源一行显示 `[FAILED] ... forced failure ... (using data from <上次成功时间>)`，其余三行 `[ok]`；`out/meta.json` 里该来源 `status` 为 `failed`，`out/river_flow.json` 的数据不变。
- 记录：2026-10-09，M1。这个行为由单元测试覆盖；命令本身还没有在真实网络下运行过。

## 4. 评分（scorer）

（暂无）

## 5. 发布（publish）

### 只校验输出文件，不上传
- 命令：`python3 -m publish.run push --out out --dry-run`
- 运行目录：项目根目录
- 前置条件：已运行过采集，`out/` 下有文件
- 预期结果：`push: 4 output files are valid`，然后 `push: --dry-run, stopping before any upload`。文件不合 Schema 时会列出问题并以错误退出。
- 记录：2026-10-09，M1。在开发环境运行过。

### 校验并发布到 Supabase
- 命令：`SUPABASE_URL=<项目地址> SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY python3 -m publish.run push --out out`
- 运行目录：项目根目录
- 前置条件：Supabase 项目已按第 8 节准备好；`SUPABASE_SERVICE_KEY` 是密钥，只放在环境变量里，不要写进任何文件
- 预期结果：三行 `push:`，分别报告校验通过、上传的文件数、`conditions_hourly` 写入的行数（两个钓点共 336 行）。
- 记录：2026-10-09，M1。这条命令在 GitHub Actions 上运行成功（写入 336 行）；在本机还没运行过。

### 取回上一次运行保存的状态
- 命令：`SUPABASE_URL=<项目地址> SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY python3 -m publish.run pull --out out`
- 运行目录：项目根目录
- 前置条件：同上
- 预期结果：`pull: N state file(s) downloaded`。第一次运行时 N 为 0，属正常。
- 记录：2026-10-09，M1。**还没有实际运行过**。

## 6. 前端（web）

（暂无）

## 7. 测试

### 运行全部单元测试
- 命令：`python3 -m pytest tests/unit -q`
- 运行目录：项目根目录
- 前置条件：已安装依赖。不需要网络，测试用的是 `tests/smoke/samples/` 里保存的真实返回。
- 预期结果：最后一行 `44 passed`。
- 记录：2026-10-09，M1。在开发环境（Python 3.13）运行过；Liang 的 Mac 上还没运行过。

### 检查已发布的数据（M1 验收用）
- 命令：`python3 tests/acceptance/check_m1.py <标签>`，例如 `python3 tests/acceptance/check_m1.py baseline`
- 运行目录：项目根目录
- 前置条件：已安装依赖；项目根目录下有一个 `.env` 文件（不会被提交），内容两行：`SUPABASE_URL=https://<项目>.supabase.co` 和 `SUPABASE_ANON_KEY=<anon public 密钥>`。anon 密钥在 Supabase 的 Project Settings → API 里，它本来就是公开的；**不要**把 service_role 密钥放进 `.env`。
- 预期结果：打印已发布文件的生成时间、覆盖范围、潮汐与 LINZ 文件的对照、三个小时的数值与 Open-Meteo 直接返回值的对照、各数据源状态、历史表行数，最后是 summary。输出同时保存到 `tests/acceptance/output/<标签>.txt`。第 4 项要在一次 Collect 运行结束后马上检查，隔久了 Open-Meteo 会更新预报，数值就对不上。
- 记录：2026-10-09，M1。脚本逻辑用保存的样本离线检查过；**还没有对着真实的 Supabase 运行过**。

## 8. 部署与定时任务

### 准备 Supabase 项目（网页操作，只做一次）
- 命令：
  1. 在 supabase.com 新建一个项目。
  2. 左侧 SQL Editor：把 `schemas/sql/conditions_hourly.sql` 的全部内容贴进去，点 Run。
  3. 左侧 Storage：New bucket，名字填 `fishing-data`，勾选 Public bucket。
  4. Project Settings → API：记下 Project URL 和 `service_role` 密钥。
  5. GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret，添加两个：`SUPABASE_URL`（Project URL）和 `SUPABASE_SERVICE_KEY`（service_role 密钥）。
- 运行目录：无
- 前置条件：有 Supabase 账号，免费档的两个项目名额还有空位
- 预期结果：SQL 运行后显示 `Success. No rows returned`；Table Editor 里出现 `conditions_hourly` 表；Storage 里出现 `fishing-data` 桶。
- 记录：2026-10-09，M1。Liang 已做完，随后的发布成功写入了数据。

### 把采集任务的工作流文件放到 GitHub 要求的位置
- 命令：`cp docs/workflows/collect.yml .github/workflows/collect.yml`
- 运行目录：项目根目录
- 前置条件：Supabase 已准备好、两个 secret 已添加，否则定时任务每次都会失败。只需做一次；以后改了 `docs/workflows/collect.yml` 要重新复制。
- 预期结果：没有输出。提交并推送后，GitHub 的 Actions 页面出现 “Collect”，之后每 3 小时自动运行一次，也可以点 Run workflow 手动运行。
- 记录：2026-10-09，M1。已使用，“Collect” 工作流手动运行成功。

### 第一次把项目推送到 GitHub
- 命令：
  ```
  git init -b main
  git remote add origin https://github.com/XiaoMaGe-hero/Fishing-Schedule.git
  git add -A
  git commit -m "M0: data source smoke tests and report"
  git push -u origin main
  ```
- 运行目录：项目根目录
- 前置条件：本机已登录 GitHub；工作流文件已复制到 `.github/workflows/`。只需做一次。
- 预期结果：最后一条命令显示 `branch 'main' set up to track 'origin/main'`。如果 GitHub 上的仓库里已经有文件（例如建仓库时勾选了 README），推送会被拒绝，先运行 `git pull origin main --allow-unrelated-histories` 再推送。
- 记录：2026-10-08，M0。实际推送时远端已有 README，按上面的办法合并后推送成功。

### 提交并推送日常改动
- 命令：
  ```
  git add -A
  git commit -m "<这次改了什么>"
  git push
  ```
- 运行目录：项目根目录
- 前置条件：已做过上面的第一次推送
- 预期结果：`git push` 最后显示 `main -> main`。
- 记录：2026-10-08，M0

## 9. 排错

记录“这样做不行，原因是什么”，以及对应的解决办法。

### 用脚本读取 ECan 的公开流量页面读不到内容
- 现象：请求 `https://www.ecan.govt.nz/data/riverflow/sitedetails/66401` 返回 HTTP 200，但内容只有约 200 字节，里面是 `_Incapsula_Resource` 脚本。
- 原因：该页面有防爬验证，只有浏览器能通过。
- 解决办法：不读页面，改用 ECan 数据目录接口，地址见 `tests/smoke/smoke_ecan.py` 里的 `DATA_URL`。
- 记录：2026-10-08，M0

### ECan 冒烟测试取到数据却报 0 个点
- 现象：`ecan` 一行显示 `data endpoint HTTP 200, 0 flow points`。
- 原因：接口返回的时间格式是 `8/10/2026 10:00:00 PM`（12 小时制），脚本原先不认识。
- 解决办法：已在 `smoke_ecan.py` 的 `DATE_FORMATS` 里加入 `%d/%m/%Y %I:%M:%S %p`。
- 记录：2026-10-08，M0


### 发布时上传失败：HTTP 404 PGRST125 "Invalid path specified in request URL"
- 现象：GitHub Actions 的 “Validate and publish” 一步报 `upload of conditions/... failed: HTTP 404 ... PGRST125`。
- 原因：`SUPABASE_URL` 里带了 `/rest/v1/` 这段路径（Supabase 后台有一处显示的地址带这个后缀），请求被发到了数据库接口而不是存储接口。
- 解决办法：`publish/run.py` 现在会自动去掉地址里的路径，只保留 `https://<项目>.supabase.co`，secret 不用改。另外，取回状态时如果列不出桶的内容，现在会直接报错，不再悄悄跳过。
- 记录：2026-10-09，M1
