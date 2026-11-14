# MI姐 Substack 独立监测（公开 RSS 通道）

- 作者主页：https://mistery0789.substack.com/
- 公开 RSS：https://mistery0789.substack.com/feed
- 采集脚本：`collect_substack.py`（Python 标准库）
- 工作流：`.github/workflows/collect-substack.yml`，每四小时检查，北京时间 08:41 有一轮
- 数据：`data/substack/YYYY-MM-DD.json`，状态：`state/substack-latest.json`
- 不改动原有 X/Nitter/Space 工作流与脚本；不使用邮件密码、OAuth Token 或付费 API
- 公开仓库只保存标题、链接、发布日期和最多 240 字公开摘要，不保存 Gmail 邮件内容、验证码、付费正文或订阅者个人信息

**限制与验收**：
1. RSS 不覆盖 Substack Notes、评论、直播或只通过订阅邮件推送的内容。
2. `complete: false` 是明确的覆盖标记；无法因为 RSS 条目为 0 就说作者没有更新。
3. 点击 Actions → Collect MI public Substack RSS → Run workflow 可手动验收；应先通过离线测试，再查看 `state/substack-latest.json` 的状态。
4. GitHub Actions 的定时触发可能延迟。若 RSS 请求遭遇 403/429，状态应记录错误，不应默默产出“今日无内容”。
5. Gmail 邮件通道与本公开仓库解耦：只在 ChatGPT 已授权的 Gmail 连接中私下读取订阅邮件，绝不将邮件凭据写入该仓库。
