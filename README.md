# italki Chinese Community Tutor 状态监控

每周一（北京时间）多次爬取 italki 支持页面，检查
**Chinese Community Tutor** 是 open 还是 closed，状态变化时立即发邮件提醒。

- 数据源：Zendesk Help Center API（绕过 Cloudflare 拦截）
- 运行环境：GitHub Actions（免费、无需开电脑）
- 提醒方式：邮件（SMTP）
- 检查频率：仅周一每 3 小时检查一次（共 7 次检查 + 1 次周报），覆盖 italki 美国时区更新窗口
- 提醒规则：状态变化→立即发【状态变化】邮件；周一 12:01 额外发一封【周报】；其余未变化则静默

---

## 一、工作原理

1. 通过 Zendesk API 获取文章
   `Is my language open for application?` 的 JSON 内容
2. 解析其中的状态表格，定位 **Chinese** 行的 **Community Tutor** 列
3. 读取上次记录的状态（`state/last_status.json`），判断是否变化
4. 按模式发送邮件（周报模式总发；检查模式仅变化时发）
5. 把当前状态提交回仓库，供下次运行比较

---

## 二、配置步骤

### 1. 准备邮箱授权码

任选一个邮箱服务商，获取 **SMTP 授权码**（不是登录密码）：

| 服务商 | SMTP_HOST | SMTP_PORT | 授权码获取方式 |
|--------|-----------|-----------|----------------|
| **QQ 邮箱** | `smtp.qq.com` | `465` | 设置 → 账户 → POP3/SMTP 服务 → 开启 → 生成授权码 |
| **163 邮箱** | `smtp.163.com` | `465` | 设置 → POP3/SMTP/IMAP → 开启 → 设置授权码 |
| **Gmail** | `smtp.gmail.com` | `465` | 账号 → 安全 → 两步验证 → 应用专用密码 |
| **Outlook** | `smtp.office365.com` | `587` | 账号安全设置（需开启两步验证） |

> 推荐使用 QQ 邮箱，配置最简单。手机安装 QQ 邮箱 App 即可及时收到推送。

### 2. 把项目推送到 GitHub

```bash
git init
git add .
git commit -m "init: italki monitor"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

### 3. 配置 GitHub Secrets

进入 GitHub 仓库页面 → **Settings** → **Secrets and variables** → **Actions**
→ **New repository secret**，依次添加以下 5 个：

| Secret 名称 | 值 |
|-------------|----|
| `SMTP_HOST` | 如 `smtp.qq.com` |
| `SMTP_PORT` | 如 `465` |
| `SMTP_USER` | 发件邮箱地址，如 `you@qq.com` |
| `SMTP_PASS` | 上一步获取的**授权码** |
| `MAIL_TO` | 收件邮箱，如 `you@qq.com`（多个用英文逗号分隔）|

### 4. 手动触发测试

进入仓库 → **Actions** → 左侧选 `Monitor italki Chinese Community Tutor`
→ **Run workflow** → 选择模式（`weekly` 发周报 / `check` 仅变化才提醒）
→ 点击运行，验证邮件能否收到。

之后将按周一每 3 小时自动运行（详见下方运行机制）。

---

## 三、本地测试

```bash
pip install -r requirements.txt

# Windows PowerShell
$env:SMTP_HOST="smtp.qq.com"
$env:SMTP_PORT="465"
$env:SMTP_USER="you@qq.com"
$env:SMTP_PASS="你的授权码"
$env:MAIL_TO="you@qq.com"
python src/monitor.py
```

运行后会在 `state/last_status.json` 生成状态文件。

---

## 四、文件说明

```
.
├── .github/workflows/monitor.yml  # GitHub Actions 定时任务
├── src/monitor.py                 # 爬虫 + 解析 + 邮件主脚本
├── state/last_status.json         # 上次状态（运行后自动生成并提交）
├── requirements.txt               # Python 依赖
└── README.md
```

---

## 五、注意事项

- **定时延迟**：GitHub Actions 免费层的 cron 可能有几分钟到几十分钟
  延迟，极端情况可能跳过。如需精确，可改用本地 Windows 任务计划。
- **运行机制**：仅周一运行 8 次（1 次周报 + 7 次检查，每 3 小时），周二至周日不运行。
  周一 12:01 CST（UTC 04:01）为周报模式（总是发邮件），其余 7 次为检查模式（仅变化时发）。
  所有 cron 已换算为 UTC，编辑 `.github/workflows/monitor.yml` 可调整。
- **文章 ID**：脚本依赖 Zendesk 文章 ID `115001499873`，若 italki 更换
  文章需更新 `src/monitor.py` 中的 `ARTICLE_URL`。
- **状态变化判断**：首次运行无历史记录，只发周报不算变化；之后每次
  与上次比较，变化则邮件标题加【状态变化】前缀。检查模式下未变化静默不发邮件。

---

## 六、日常维护备忘

### 1. 改什么、改哪里对照表

| 想改什么 | 改哪里 | 是否要 push 代码 | 是否立即生效 |
|---|---|---|---|
| **收件邮箱** | GitHub Secrets 的 `MAIL_TO` | ❌ | ✅ 下次运行即用新值 |
| **发件邮箱 / 授权码 / SMTP 主机端口** | GitHub Secrets 的 `SMTP_USER` / `SMTP_PASS` / `SMTP_HOST` / `SMTP_PORT` | ❌ | ✅ |
| **定时时间** | [`.github/workflows/monitor.yml`](.github/workflows/monitor.yml) 的 `cron:` 行 + MODE 联动行（见下方） | ✅ 必须 commit+push | 下次到点才生效 |
| **监控的语言** | [`src/monitor.py`](src/monitor.py) 顶部 `TARGET_LANGUAGE`（默认 `"Chinese"`） | ✅ | 下次运行即用新值 |
| **监控的角色** | [`src/monitor.py`](src/monitor.py) 顶部 `TARGET_ROLE`（默认 `"Community Tutor"`） | ✅ | 下次运行即用新值 |
| **监控的文章 ID** | [`src/monitor.py`](src/monitor.py) 顶部 `ARTICLE_URL` / `ARTICLE_WEB_URL` | ✅ | 下次运行即用新值 |
| **重试次数 / 超时** | [`src/monitor.py`](src/monitor.py) `fetch_article` 中的 `MAX_RETRIES` / `TIMEOUT` | ✅ | 下次运行即用新值 |

### 2. 改定时的具体步骤

打开 [`.github/workflows/monitor.yml`](.github/workflows/monitor.yml)，看顶部 `schedule:` 下的 cron 行。

**时区换算公式**：CST（中国时间）→ UTC（cron 用）= CST 小时数 − 8

| 想要的中国时间 | 对应 UTC | cron 写法 |
|---|---|---|
| 周一 12:01 | 周一 04:01 | `1 4 * * 1` |
| 周一 18:00 | 周一 10:00 | `0 10 * * 1` |
| 周二 09:30 | 周二 01:30 | `30 1 * * 2` |

⚠️ **改完 cron 后，必须同步更新 MODE 联动行**（`Determine mode` 步骤里）：

```yaml
elif [ "${{ github.event.schedule }}" = "1 4 * * 1" ]; then
```

把这里的双引号字符串改成你新的周报 cron。否则周报会被识别成 check 模式，状态没变化就**静默不发邮件**——这是"邮件没收到"最常见的原因。

### 3. 修改代码后的标准 push 流程

```powershell
cd "d:\OneDrive\财源滚滚\2025礼包在手\AI projects\monitor_italki\demo"
git add <改的文件>
git commit -m "chore: 描述改动"
git pull --rebase origin main   # 先拉云端 Actions 自动 commit 的 state，避免冲突
git push origin main             # 本地代理已配，自动走 Clash 7890 端口
```

> 关键习惯：云端 Actions 每次跑都会自动 commit `state/last_status.json`，所以本地直接 push 经常被拒。养成"先 `git pull --rebase` 再 `git push`"的习惯即可避免。
> 若 push 报 `Connection was reset`：确认 Clash 已启动且 7890 端口可用（已配本地代理，会自动走）。

### 4. 邮件没收到时的排查清单

1. **看 Actions 运行日志**：仓库 → Actions → 点最近一次运行 → 拉 "Run monitor" 步骤输出 → 看最后一行
   - `邮件已发送: ...` → 邮件已发出，去 QQ 邮箱**垃圾邮件**文件夹找
   - `状态未变化（...），check 模式静默，不发邮件` → MODE 没传成 weekly（手动触发时下拉选 weekly）
   - `缺少环境变量: ['SMTP_PASS']` → Secrets 漏配或拼写错
   - `smtplib.SMTPAuthenticationError: 535` → 授权码错或 SMTP 服务未开启
2. **检查 GitHub Secrets**：仓库 → Settings → Secrets and variables → Actions，确认 5 个都有且拼写正确
3. **检查 QQ 邮箱垃圾邮件**：QQ 邮箱对自动发来的邮件很敏感
4. **本地测试 SMTP**：在本地 PowerShell 设置环境变量后跑 `python src/monitor.py`（注意本地 Python 3.6 可能 SSL 失败，仅供参考）