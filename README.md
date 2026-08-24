# italki Chinese Community Tutor 状态监控

每周一（北京时间）多次爬取 italki 支持页面，检查
**Chinese Community Tutor** 是 open 还是 closed，状态变化时立即发邮件提醒。

- 数据源：Zendesk Help Center API（绕过 Cloudflare 拦截）
- 运行环境：GitHub Actions（免费、无需开电脑）
- 提醒方式：邮件（SMTP）
- 检查频率：仅周一每 3 小时检查一次（共 8 次），覆盖 italki 美国时区更新窗口
- 提醒规则：状态变化→立即发【状态变化】邮件；周一 00:00 额外发一封周报；其余未变化则静默

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
- **运行机制**：仅周一运行 8 次（每 3 小时），周二至周日不运行。
  周一 00:00 为周报模式（总是发邮件），其余 7 次为检查模式（仅变化时发）。
  所有 cron 已换算为 UTC，编辑 `.github/workflows/monitor.yml` 可调整。
- **文章 ID**：脚本依赖 Zendesk 文章 ID `115001499873`，若 italki 更换
  文章需更新 `src/monitor.py` 中的 `ARTICLE_URL`。
- **状态变化判断**：首次运行无历史记录，只发周报不算变化；之后每次
  与上次比较，变化则邮件标题加【状态变化】前缀。检查模式下未变化静默不发邮件。