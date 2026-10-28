# MI姐 X 动态监测（实验版）

目标：免费采集 X 账号 **@wr0789** 的原创推文、引用和本人回复，按北京时间保存，供每日复盘使用。

**当前状态：仅完成部署，尚未验证能读取账号内容。** 使用开源 [Twikit](https://github.com/d60/twikit) 而非付费 X API，可能遭遇登录验证、限流和接口变更。

## 测试方法
前往 [Actions](https://github.com/lilyQ-stack/mi-x-monitor/actions/workflows/collect.yml)，选择 **Collect MI activity → Run workflow**。
在没有登录会话时，执行安全预检，并将结果写入 `state/latest.json`，状态为 `needs_auth`；这**不代表账号没有发帖**。

## 后续采集
采集器 `collector.py` 可以使用授权的 X 会话。可选择为专用 X 账号配置 GitHub Actions Secret `X_COOKIES_BASE64`（Twikit cookies JSON 的 base64 文本）。
**绝对不要在聊天里发送密码、Cookie 或令牌，不要提交到公开仓库；使用独立账号并注意平台的自动访问规则及账号风控。**

采集结果仅公开帖子ID、原帖URL、时间、类型与最多120字符摘录，不发布完整推文、评论或音频文件。首次只抓各时间线第一页，`complete=false`，即使帖子数量为零，也不能断言没有发帖。

工作流每日北京时间08:10及20:10尝试运行。GitHub 定时任务可能延迟；公开仓库中的标准 GitHub 托管 Actions 通常不收运行分钟费，但 **X 的限流不会因此消失**。

## 验收
首先验证 Actions 可以运行并写入 `state/latest.json`，然后才考虑独立账号和会话。最终要用2026年10月27日已知帖子比对覆盖率；在验证前不把采集结果当作完整日报。
