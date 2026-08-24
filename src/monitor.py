#!/usr/bin/env python3
"""
italki Chinese Community Tutor 开放状态监控

通过 Zendesk Help Center API 爬取 italki 支持文章
"Is my language open for application?"，解析表格中
Chinese Community Tutor 的状态（open/closed），与上次
记录的状态比较后发送邮件提醒。

环境变量（通过 GitHub Secrets 注入）：
    SMTP_HOST  SMTP 服务器地址，如 smtp.qq.com
    SMTP_PORT  SMTP 端口，465(SSL) 或 587(STARTTLS)
    SMTP_USER  发件邮箱地址
    SMTP_PASS  邮箱授权码（非登录密码）
    MAIL_TO    收件邮箱，多个用英文逗号分隔
"""
import json
import os
import re
import smtplib
import sys
import time
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import requests

ARTICLE_URL = (
    "https://support.italki.com/api/v2/help_center/en-us/"
    "articles/115001499873.json"
)
ARTICLE_WEB_URL = (
    "https://support.italki.com/hc/en-us/articles/"
    "115001499873-Is-my-language-open-for-application"
)
TARGET_LANGUAGE = "Chinese"
TARGET_ROLE = "Community Tutor"
STATE_FILE = Path("state/last_status.json")
CST = timezone(timedelta(hours=8))


def fetch_article(retries=4):
    """通过 Zendesk API 获取文章，返回 article dict。

    自动重试：对偶发的 SSL/连接/超时错误最多重试 4 次，每次间隔 2 秒。
    """
    headers = {"User-Agent": "Mozilla/5.0 (monitor-italki-bot/1.0)"}
    last_err = None
    for i in range(retries):
        try:
            r = requests.get(ARTICLE_URL, headers=headers, timeout=60)
            r.raise_for_status()
            data = r.json()
            if "article" not in data:
                raise ValueError(f"API 返回异常，顶层键: {list(data.keys())}")
            return data["article"]
        except (
            requests.exceptions.SSLError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as e:
            last_err = e
            print(f"第 {i + 1}/{retries} 次爬取失败: {type(e).__name__}: {e}")
            if i < retries - 1:
                time.sleep(2)
    raise last_err


def _cell_text(html):
    """去掉 HTML 标签，返回纯文本"""
    return re.sub(r"<[^>]+>", "", html).strip()


def parse_table(body):
    """解析文章 body 中的状态表格，返回 {语言: {角色: 状态}}"""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S)
    if not rows:
        raise ValueError("未找到表格行")
    header = [_cell_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", rows[0], re.S)]
    if len(header) < 3:
        raise ValueError(f"表头列数不足: {header}")
    result = {}
    for row in rows[1:]:
        cells = [_cell_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if not cells:
            continue
        lang = cells[0]
        if not lang:
            continue
        result[lang] = {
            header[i]: cells[i].lower()
            for i in range(1, min(len(header), len(cells)))
        }
    return result


def get_target_status(body):
    """获取 Chinese Community Tutor 的状态"""
    table = parse_table(body)
    if TARGET_LANGUAGE not in table:
        raise ValueError(
            f"表格中未找到 '{TARGET_LANGUAGE}'，已有语言: {list(table.keys())[:10]}..."
        )
    row = table[TARGET_LANGUAGE]
    if TARGET_ROLE not in row:
        raise ValueError(f"未找到角色 '{TARGET_ROLE}'，该行列: {row}")
    return row[TARGET_ROLE]


def extract_week_range(body):
    """提取当前周的日期范围，如 'August 17th - 23rd, 2026'"""
    m = re.search(r"([A-Z][a-z]+\s+\d+\w*\s*-\s*\d+\w*,?\s*\d{4})", body)
    return m.group(1).strip() if m else "未知"


def load_last_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return None


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def send_email(subject, html, cfg):
    """发送邮件，端口 465 用 SSL，其它用 STARTTLS"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["SMTP_USER"]
    msg["To"] = cfg["MAIL_TO"]
    msg.attach(MIMEText(html, "html", "utf-8"))
    port = int(cfg["SMTP_PORT"])
    recipients = [a.strip() for a in cfg["MAIL_TO"].split(",") if a.strip()]
    if port == 465:
        with smtplib.SMTP_SSL(cfg["SMTP_HOST"], port, timeout=30) as s:
            s.login(cfg["SMTP_USER"], cfg["SMTP_PASS"])
            s.sendmail(cfg["SMTP_USER"], recipients, msg.as_string())
    else:
        with smtplib.SMTP(cfg["SMTP_HOST"], port, timeout=30) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(cfg["SMTP_USER"], cfg["SMTP_PASS"])
            s.sendmail(cfg["SMTP_USER"], recipients, msg.as_string())


def build_email(current, week, last_status, checked_at, changed, error=None):
    """构造邮件主题与 HTML 正文"""
    if error:
        subject = "【监控异常】italki 爬取失败"
        body = (
            f"<h2>⚠️ 监控脚本执行异常</h2>"
            f"<p>检查时间：{checked_at}</p>"
            f"<p>错误信息：</p>"
            f"<pre style='background:#f4f4f4;padding:12px;border-radius:4px;"
            f"white-space:pre-wrap;'>{error}</pre>"
            f"<hr><p>文章链接：<a href='{ARTICLE_WEB_URL}'>{ARTICLE_WEB_URL}</a></p>"
        )
        return subject, body

    cur_label = "🟢 OPEN" if current == "open" else "🔴 CLOSED"
    if last_status:
        last_label = "🟢 OPEN" if last_status == "open" else "🔴 CLOSED"
    else:
        last_label = "（首次运行，无历史记录）"

    if changed:
        prefix = "【状态变化】"
        change_note = (
            '<p style="color:#c0392b;font-size:18px;font-weight:bold;">'
            "⚠️ 状态已变化，请及时关注！</p>"
        )
    else:
        prefix = "【周报】"
        change_note = (
            '<p style="color:#27ae60;">状态与上次相同，未发生变化。</p>'
        )

    subject = f"{prefix} Chinese Community Tutor = {current.upper()}（{week}）"
    body = f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#333;">
      <h2 style="margin-bottom:4px;">italki Chinese Community Tutor 状态监控</h2>
      <table border="0" cellpadding="8" cellspacing="0"
             style="border-collapse:collapse;font-size:15px;margin:12px 0;">
        <tr><td style="color:#666;">当前状态：</td>
            <td style="font-size:22px;font-weight:bold;">{cur_label}</td></tr>
        <tr><td style="color:#666;">上次状态：</td><td>{last_label}</td></tr>
        <tr><td style="color:#666;">本周范围：</td><td>{week}</td></tr>
        <tr><td style="color:#666;">检查时间：</td><td>{checked_at}</td></tr>
      </table>
      {change_note}
      <hr style="border:0;border-top:1px solid #eee;margin:16px 0;">
      <p style="font-size:13px;">
        文章链接：<a href="{ARTICLE_WEB_URL}">{ARTICLE_WEB_URL}</a>
      </p>
      <p style="color:#999;font-size:12px;">本邮件由 GitHub Actions 自动发送</p>
    </div>
    """
    return subject, body


def main():
    cfg = {
        k: os.environ.get(k)
        for k in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "MAIL_TO"]
    }
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        print(f"缺少环境变量: {missing}")
        sys.exit(1)

    checked_at = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S CST")

    try:
        article = fetch_article()
        current = get_target_status(article["body"])
        week = extract_week_range(article["body"])
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        print(f"爬取失败: {err}")
        subject, html = build_email(None, "未知", None, checked_at, False, error=err)
        send_email(subject, html, cfg)
        sys.exit(2)

    mode = os.environ.get("MODE", "check")
    print(f"运行模式: {mode}")

    last = load_last_state()
    last_status = last["status"] if last else None
    changed = last_status is not None and last_status != current

    print(
        f"当前状态: {current} | 上次状态: {last_status} | "
        f"变化: {changed} | 周: {week}"
    )

    should_send = changed or (mode == "weekly")
    if should_send:
        subject, html = build_email(current, week, last_status, checked_at, changed)
        send_email(subject, html, cfg)
        print(f"邮件已发送: {subject}")
    else:
        print(f"状态未变化（{current}），check 模式静默，不发邮件")

    save_state({"status": current, "week": week, "checked_at": checked_at})
    print("状态已保存到 state/last_status.json")


if __name__ == "__main__":
    main()