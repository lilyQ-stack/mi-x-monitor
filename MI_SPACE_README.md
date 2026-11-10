# MI姐 X Space 自动采集（独立工作流）

该功能与当前推文采集分开运行，不修改 collect_nitter.py、collector.py 或既有 GitHub Actions 工作流。

## 自动流程

1. 北京时间约05:35、11:35、17:35、23:35，检查近期 data/nitter-YYYY-MM-DD.json 里经核验的 MI姐 Space 链接，另外用10月31日和11月6日的已知链接进行初始下载测试。
2. 不使用用户账号和Cookie，通过 yt-dlp 尝试下载有公开回放的录音；每次至多处理一场，失败最多重试3次、间隔至少24小时。
3. 成功下载后，使用 faster-whisper 中文small模型在GitHub Actions CPU上生成带时间戳的自动逐字稿。自动转写会有错字和数字识别错误，必须复核。
4. 公开仓库仅保存 state/mi-space-status.json（状态、错误、尝试次数和Artifact所在运行ID）；不提交录音或完整逐字稿。
5. 逐字稿保留为对应工作流运行的 GitHub Actions Artifact，名称 mi-space-transcript-<run_id>，保留14天。可用GitHub连接器按运行ID获取。
6. 工作流页面：https://github.com/lilyQ-stack/mi-x-monitor/actions/workflows/mi-space-transcribe.yml

## 重要限制

- X可能阻止未登录的下载工具，或关闭Space回放。工作流成功运行不等于录音成功；必须核查每条记录是否 status=transcribed 以及 Artifact 是否存在。
- status=download_failed 不代表MI姐没有做Space，也不能用此推断当天没有语音。
- 未通过推文或公开RSS提供链接的新Space不会被本流程发现。可在GitHub Actions手动运行时提供一个公开Space URL。
- 这是公开仓库，GitHub Actions Artifact不应视为私密存储；如果需要保留完整文本且限制他人访问，未来应迁移到独立私有仓库。
- GitHub scheduled workflow 可能延迟；14天后原始逐字稿Artifact会过期。
- 只下载公开提供回放的内容，不获取私人或付费内容，不要求用户提交X密码、Cookie或令牌。
- 首次验收：必须看到实际成功下载并转写，或者明确记录失败原因。仅成功上传脚本不代表X下载能力已验证。
