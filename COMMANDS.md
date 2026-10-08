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
- 预期结果：显示 3.9 或更高。M0 的冒烟脚本只用标准库，不需要 `pip install`。
- 记录：2026-10-08，M0

## 2. 数据源冒烟测试（tests/smoke）

`run_all.py` 在 2026-10-08 由 Liang 在 Mac 上实际运行过（Python 3.12.12），linz、weather、marine 通过。ecan 当时因脚本不认识时间格式而失败，脚本已修复，待重跑。复制工作流文件和 GitHub Actions 两条还没有实际用过。

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
- 记录：2026-10-08，M0；写入时还没有实际用过。

### 在 GitHub Actions 上运行 ECan 冒烟测试
- 命令：在 GitHub 网页上操作：仓库 → Actions → “M0 smoke - ECan” → Run workflow。装了 `gh` 的话也可以用 `gh workflow run smoke-ecan.yml`。
- 运行目录：项目根目录（用 `gh` 时）
- 前置条件：工作流文件已复制到 `.github/workflows/`（见上一条），代码已推送到 GitHub 仓库
- 预期结果：任务结束后，在该次运行页面底部下载 `smoke-output`，里面的 `ecan-github.txt` 最后一行是 `RESULT: PASS` 或 `RESULT: FAIL`，说明 ECan 是否接受来自 GitHub Actions 的请求。
- 记录：2026-10-08，M0

## 3. 采集（collector）

（暂无）

## 4. 评分（scorer）

（暂无）

## 5. 发布（publish）

（暂无）

## 6. 前端（web）

（暂无）

## 7. 测试

（暂无）

## 8. 部署与定时任务

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
- 记录：2026-10-08，M0；写入时还没有实际用过。

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
