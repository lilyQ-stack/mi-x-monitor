# MI姐 Substack 独立监测 — 测试阶段

- 作者主页：https://mistery0789.substack.com/
- 公开 RSS：https://mistery0789.substack.com/feed
- 采集脚本：`collect_substack.py`（Python 标准库）
- 独立工作流：`.github/workflows/collect-substack.yml`
- 数据：`data/substack/YYYY-MM-DD.json`，状态：`state/substack-latest.json`
- 不改动 X/Nitter/Space 工作流；不使用 Gmail 密码、OAuth Token 或付费 API
- 公开仓库仅允许保存公开标题、链接、发布日期和短摘要，不保存任何私密邮件或验证信息

## 2026-11-14 首次验收
- GitHub Actions 运行：[#43568573060](https://github.com/lilyQ-stack/mi-x-monitor/actions/runs/43568573060)
- 离线 XML 解析 / 日期转换 / 去重测试全部通过。
- 在线抓取出现 `HTTP 403 Forbidden`，说明 GitHub 托管服务器无法直接获取当前 Substack RSS。
- 已**暂停定时触发**（保留 `workflow_dispatch` 手动诊断），避免每天重复失败/无效消耗免费 Actions 运行时间。
- 尚未形成可信的自动文章采集；不能将状态 `error` 解释为作者无内容。
- 邮件通道应使用用户授权的 Gmail 私下读取。Gmail 连接到 ChatGPT 并不等于 GitHub Actions 自动取得 Gmail 权限，不能复制 Gmail 的访问令牌。
- 当前 ChatGPT 的 5 个活跃定时任务名额已满；新增独立 Gmail 定时核验需要释放一个名额，或改用用户单独授权的免费 Google Apps Script 时间触发器。

## 覆盖边界
RSS 和邮件均不保证覆盖 Notes、评论、直播、Space 或付费内容。邮件要先实际收到一封可核验的文章邮件，才能验收发件人匹配、正文/链接提取及去重规则。任何采集错误都应明确标记，不能产出虚假的“今日无内容”。
