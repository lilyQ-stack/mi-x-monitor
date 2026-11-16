# MI姐 Substack Notes 合规采集研究：实验分支，未启用

日期：2026-11-16；目标作者：mistery0789。

## 核验结果
- 现有 GitHub RSS 实验返回 HTTP 403，仍保留手动触发，不重启定时抓取。
- Gmail 已收到 MI姐部分文章和直播通知，但不会完整覆盖 Notes、回复和转发。
- 原有 X / Nitter / Space / Gmail 项目一律不修改。
- 此分支不调用任何 Substack 网站或接口，也不读取任何登录 Cookie。

## 技术研究候选（基于实际 README 和 GitHub 元数据）
1. https://github.com/jakub-k-slys/substack-gateway-oss
   2026-11-16 约 41 Stars / 10 Forks；MIT 许可。
   项目说明支持 get_profile_notes(slug, cursor)，公开作者 Notes 的分页读取，文档称无需 Cookie。
   其 GitHub CI/E2E 最近有成功记录，但这并不能证明特定作者或 GitHub 托管 IP 一定能抓取。
2. https://github.com/alialfredji/substack-api
   公开 API 技术研究和游标分页文档。用户量极少，保留作参考。
3. 高 Star 的 Substack2Markdown / sbstck-dl 主要处理长文章，不符合 Notes 的核心任务。

## 法律及授权关卡
- Substack 使用条款对未经许可的抓取/自动复制有限制；开源项目许可证不是 Substack 的数据访问许可。
- 已在用户的 Gmail 准备向 Substack 咨询「单一作者、非商业、低频、仅 URL/日期/类型/读者摘要」的邮件草稿；必须由用户审核并主动发送。
- 获得明确允许的数据访问方式之前，不上线针对 Notes 的自动请求；不绕过403、验证码或付费墙。
- 如果后来希望保存完整正文，还需要另外评估作者著作权、授权范围、保存期限与删除要求。

## 目前可用：离线导入，不联网
substack_notes_import.py 接收由用户手动记录或获授权来源交付的 CSV。

列名：author_handle,url,published_at,kind,reader_summary

示例（示意链接，并非真实 Notes）：
mistery0789,https://substack.com/@mistery0789/note/c-123,2026-11-15,note,我自己写的观点摘要

调用方式：
python substack_notes_import.py --input my_notes.csv --output my_private_notes.json

测试方式：
python -m unittest test_substack_notes_import.py -v

输出应放在用户私密位置，不应提交到公开 GitHub 仓库。脚本不对作者身份作事实核验，不宣称采集完整。

## 后续准入和验收
- 收到书面许可或官方明确支持的数据接口说明，核对适用范围、访问频率和保存规则。
- 核实目标作者身份和真实链接；对 Notes 分页、时区、发布日期与去重进行测试。
- 区分作者原创 Note、回复、转发、长文章和直播；未知类型标记 unknown。
- 将采集结果与 App 看到的当日记录抽样比对，计算可量化覆盖率。
- 每次运行明确状态：complete / partial / error；不能把 0 条直接解释成作者当天没发言。
- 只在独立分支测试，不影响现有 X 或其他采集任务。


## 2026-11-16 Gateway OSS 源码审计（已完成）
- profile slug 到 ID：gateway_profiles/service.py 的 get_profile_id_by_slug -> user/{slug}/public_profile。
- Notes 分页：gateway_notes/service.py 的 get_notes_for_profile -> reader/feed/profile/{profile_id}?types=note，并可传 cursor。
- REST：/api/v1/profiles/{slug}/notes；MCP：get_profile_notes(slug, cursor)。
- 注意实际简化输出 NotesPageResponse 的字段只有 items / next；每条 NoteResponse 只有 id、body、likes_count、author、published_at。
- 原始 SubstackNote 模型存在 type、entity_key、parentComments 等字段，但经过 NoteResponse.from_substack 简化输出时被丢弃。
- 因而不能可靠分类原创、回复、转发；也不能凭 ID 虚构标准原帖链接。
- NoteResponse 通过 context.users[0] 设置作者；其归属需与实际页面逐条核对。
- 仓库 CI/E2E 绿色不能证明特定作者可实时访问：E2E 配置缺失时有 pytest.skip 流程。

## 新增的独立离线审计
- substack_notes_gateway_audit.py 只接收由用户合法取得、预先保存的 Gateway JSON 分页文件，绝不发 HTTP 请求。
- 从每条记录只导出 ID、作者标识、北京时间；不会复制正文，不会凭空补 URL 或帖子类型。
- 拒绝作者不匹配、ID 失效、时间无时区等数据；检测跨页重复和末页未读尽游标。
- 即使末页 next 为 null，也不宣称历史记录完整；status 固定 offline_partial。
- 运行：python substack_notes_gateway_audit.py --input permitted_page1.json permitted_page2.json --output my_private_audit.json
- 测试：python -m unittest test_substack_notes_import.py test_substack_notes_gateway_audit.py -v
- 新增独立 workflow 仅在实验分支执行离线测试；不调用 Substack，也不干扰 X 采集。


## 补充：上游原始数据结构与漏抓风险（2026-11-16）

上游源代码与样本：
- https://github.com/jakub-k-slys/substack-gateway-oss/blob/main/packages/gateway_notes/src/gateway_notes/service.py
- https://github.com/jakub-k-slys/substack-gateway-oss/blob/main/packages/gateway_notes/src/gateway_notes/schemas.py
- https://github.com/jakub-k-slys/substack-gateway-oss/blob/main/packages/gateway_core/src/gateway_core/models/substack.py
- https://github.com/alialfredji/substack-api/blob/main/docs/UPSTREAM.md

### 经代码核对的重要限制
1. Gateway OSS 读取指定用户 Notes 时固定传入 types=note；不能证明含用户在别人动态下的回复、转发、直播聊天，get_profile_notes 不等于全部发言。
2. 上游 SubstackNote 原始模型可带 type、entity_key、context、comment、post、parentComments，但简化 NoteResponse 不包含 type、post、parentComments，无法直接可靠分类。
3. 上游示例全部展示 parentComments 为空的 Notes，没有真实用户回复或转发测试样本；即使非空，也只能作为线程上下文信号，不能无验证就判定为回复。
4. context.users[0] 不必然是 Note 正文作者，comment.handle 若有可提供更强归属线索，但仍需页面核验。
5. 第三方项目的 GitHub E2E 支持缺少 SUBSTACK_* 配置时跳过；成功绿灯不是实抓 MI 姐成功的证据。
6. 第三方研究文档强调 API 会静默降级、游标可能重复或失效；在线阶段必须停止循环并标记 partial，而不是将空结果视为零发言。

### 新增原始数据离线审计
substack_notes_raw_audit.py 接受事先通过允许方式获得的原始分页 JSON（items / nextCursor），**不会联网**。

- 核对 comment.id 与 entity_key 是否对应，并拒绝明显无法确认作者的条目。
- 转换北京时间、检查重复 ID、分页游标循环、页面连接问题。
- 只输出 upstream_type、parentComments 是否存在、post 是否存在等证据元数据；原创、转发、回复一律继续标记 unverified。
- 不保留原文 body 或付费内容，也不虚构原帖 URL。
- 运行：python substack_notes_raw_audit.py --input permitted_raw1.json permitted_raw2.json --output my_private_raw_audit.json
- 验证：python -m unittest test_substack_notes_raw_audit.py -v

### 仍未解决
真实 MI 姐 Notes 的在线访问；回复和转发覆盖率；许可来源；由 ID 核验规范原帖 URL。暂不可宣布监控已上线。


## 2026-11-16 新发现：Open RSS 真实测试及正式限制

来源：
- https://openrss.org/feeds/substack
- https://openrss.org/guides/fixing-feed-issues
- https://openrss.org/guides/open-feeds
- https://openrss.org/guides/using-a-self-hosted-feed-reader

### 真实数据测试
- 2026-11-16 北京时间16:33：单次测试从 https://openrss.org/substack.com/@mistery0789 返回 HTTP 200 和有效 RSS，首次5条。
- 16:36：独立实验工作流将10条公开链接/时间/类型线索保存到本实验分支 data/substack_notes/observed.json，state/substack-openrss-latest.json 中 complete=false。
- 6条 Notes 动态、4篇文章；其中4条 Notes 的 RSS 标题前缀为 Commented on（只是疑似回复，不作已核实事实）。
- 两次快照的数量不同，说明单次RSS快照不代表完整历史，也可能存在延迟/增量加载。
- 只保留链接和日期，不存全文、Cookie、付费正文。
- 成功的执行记录：https://github.com/lilyQ-stack/mi-x-monitor/actions/runs/43832526115

### 注意：Open RSS 官方明确限制用途
- Open RSS 面向 RSS 阅读器，不支持 AI 工具、机器人或聚合服务消费，可能封禁不合规使用（参见 fixing-feed-issues 的 Unsupported usage）。
- 不应把本实验 workflow 改为自动定时监控，更不应通过切换 IP 绕过限制。
- 原工作流没有 schedule，只有 workflow_dispatch 或实验分支文件触发，正式运行仍暂停。
- 可以建议用户用其官方认可的 RSS 阅读器订阅公开源，作为个人阅读渠道，但不得误称可直接自动导入我们的日报。

### 下一种可能的授权技术渠道：API Direct
- https://apidirect.io/docs/substack-user-activity
- 提供作者 user/activity 编程接口，返回 note/post/reply/restack 等公共活动及规范链接，费用说明为50次/端点/月免费，超出部分按每页收费。
- 默认活动列表不包括 reply；必须另取 type=reply，按实际容量可能超出免费额度。
- https://apidirect.io/terms 第10条仍要求使用者遵守底层平台规则，且不保证完整性或实时性；使用第三方 API 不等于自动免除 Substack 的条款风险。
- 尚未注册/连接/调用该服务；不得伪称能获取MI姐全量发言。
