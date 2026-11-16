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
