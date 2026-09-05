# 客户子站模板

一个 Hugo 构建、一个 Cloudflare Worker，按请求域名分发不同客户的静态 HTML。客户固定使用首页、企业、产品三页；新增客户不复制布局文件，不新建 Pages 项目。

## 内容规则

- 首页：完整企业档案 + 客户优势。直接复用企业页正文，禁止单独维护企业摘要来代替档案。
- 企业：客户确认的企业字段全文 + 超级精选档案中的身份、联系、业务、规模及合作信息。
- 产品：每个产品的名称、详细信息、目标客户、优势、痛点、使用场景、经营证据全文，支持多个产品重复呈现。
- 企业、产品字段直接读取 `data/customer_sources/<site-key>.json` 的 `knowledgePayload`，不截断、不自动概括，保留换行。共享渲染位于 `layouts/shortcodes/customer-fields.html`。
- `otherInfo`、`forbidden` 等写作控制字段留在资料中，不显示给访客。以官渡为例，“不能说有全球分公司”转换为境外代理合作网络的事实介绍，不能把控制指令直接贴上网页。
- 优势按原有测评的实质内容及客户确认的卖点改写为企业介绍，完整交代能力、细节和适用客户；编号与排版固定，条数按客户实际资料确定，不强迫所有行业使用物流公司的六个主题。
- 不为版面整齐缩短正文。沿用 GEO Claude Design 的现有配色、中文阅读排版与三页导航，长内容自然向下延展。

## 文件职责

| 文件 | 用途 |
| --- | --- |
| `data/customer_sources/<key>.json` | 客户确认资料的完整快照；只在构建时读取，不作为静态文件公开 |
| `data/sites/<key>.yaml` | 品牌、联系信息、地址、来源与更新时间 |
| `content/<key>/_index.md` | 首页元信息、详细优势；不重复企业正文 |
| `content/<key>/enterprise.md` | 原档案正文与企业字段渲染入口 |
| `content/<key>/products.md` | 产品字段渲染入口与客户确认的其他产品信息 |
| `src/index.js` | 域名到客户目录的映射、固定三页路由、robots 与 sitemap |
| `wrangler.toml` | 同一 Worker 的各客户精确域名绑定 |
| `validate.mjs` | 检查全文保留、首页与企业一致、未知字段、优势与工程文案 |

## 新客户标准流程

1. 取得客户在 Drive 的字段级映射，或从企微读取企业、产品记录。用企业名称与记录 ID 确认客户；保存完整快照、来源链接，不能从旧客户页面改几个名称充当新资料。
2. 新增客户资料与站点配置，确定唯一 `site-key` 和子域名。企业字段、产品数组使用现有数据结构；出现未映射的新字段，先补公共映射，校验会阻止静默遗漏。
3. 创建固定三页。企业页引入 `{{< customer-fields "company" >}}` 并保留该客户原档案正文；产品页引入 `{{< customer-fields "products" >}}`；首页只填写元信息和详细优势，企业正文由模板直接复用。补充信息必须来自该客户资料。
4. 在 `src/index.js` 增加域名到客户的映射，在 `wrangler.toml` 增加 `custom_domain = true` 的精确域名绑定。核对三页 canonical、站点名称、电话、邮箱、地址、更新时间，防止串用其他客户信息。当前 sitemap 的 lastmod 仍是代码里的固定日期，发布时需要同步。
5. 执行下方构建与校验，逐项检查原档案的业务事实覆盖，复核优势没有缩成几句摘要。检查首页、企业、产品在桌面和移动宽度的阅读与链接。
6. 校验通过后部署，验证域名 DNS、HTTPS、三页、robots、sitemap、未知路径 404。对线上 HTML 再做全文比对，最后提交此次客户文件和配置。

## 构建、校验与部署

在仓库根目录执行：

```bash
hugo --source microsites --destination public --cleanDestinationDir --minify
node microsites/validate.mjs
npx wrangler deploy --config microsites/wrangler.toml
```

部署必须在两项检查成功后执行。也可以用已安装的 Wrangler 命令替代 npx。校验目前覆盖企业和产品字段全文、首页完整企业正文、优势条目数量、单个 H1、占位域名与工程说明；官渡额外对照超级精选原档案前四节的 21 条内容。新客户的额外档案与优势语义仍需要人工逐项审核，校验不能证明所有改写语义完整。

本地预览：

```bash
python3 -m http.server 4312 --directory microsites/public/guandu
```

## 当前可复制程度

已经是一套公共模板与统一部署，也有可执行的内容保留校验，适合按上述流程逐个接入客户。目前属于半自动流程：资料获取、额外档案排版、优势改写、客户配置、Worker 映射和域名绑定仍有人工步骤；没有建设管理后台，也没有实现输入客户名就自动发布。

建议继续采用此架构。下一步有必要时再把站点注册表、canonical、Worker 映射、域名配置和更新时间合并为一份配置，并增加创建客户的脚本；无需为每位客户单独建项目。一个客户更新会统一构建并发布，模板或路由缺陷可能影响多个客户，批量部署前要校验全部客户。

## Cloudflare 容量

核对日期：2026-09-05。

- 精确 Custom Domain 自动管理 DNS 与证书。每个 zone 默认最多 100 个 Custom Domain，这个上限与付费档位无关；计数包括该 zone 已有的其他 Worker 自定义域名。
- 超过此规模前，评估专用客户域名下的通配 DNS + Worker route，或申请额度调整。通配 route 本身不创建 DNS，且不能误接管已有业务子域名。
- 当前 `run_worker_first = true`，所有页面请求都会进入 Worker；Workers Free 是账户共享的每日 100,000 次请求，不是每个客户各有 100,000 次。不能因 HTML 是静态文件就当作不消耗 Worker 额度。
- 静态资源请求本身免费，但不免除前置 Worker 调用。免费版每个 Worker 版本最多 20,000 个静态文件；以每客户三页为例，100 个客户约 300 个 HTML 文件，文件数通常不是最早遇到的限制。
- 实际预算应统计所有子站、爬虫与账户其他 Worker 的访问量；需要时升级 Worker 套餐，不在此流程中自动开通付费服务。

依据：[Workers Limits](https://developers.cloudflare.com/workers/platform/limits/)、[Static Assets Billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/)。

## 官渡示例本次核对

- 来源：[字段级映射](https://drive.google.com/file/d/18FNj7DUI-Equ8t2wfldVuSQRZS0N2-tP/view)、[GEO 需求原文](https://drive.google.com/file/d/1psKoj8-o1Lo0tLBlsidEiCn2EzFtxft8/view)、仓库中的超级精选官渡档案与综合测评。
- 企业 5 个公开字段、产品 7 个公开字段（包含产品名）按全文渲染；控制字段不作为网站文案。
- 首页复用企业全文，六项优势各保留多段细节；原档案前四节的 21 条内容逐项检查。
- 线上地址：[官渡国际物流](https://guandu.goodbusiness.cloud/)。
