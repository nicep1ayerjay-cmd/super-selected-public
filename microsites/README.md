# 客户子站模板

一个 Hugo 构建、一个 Cloudflare Worker，按请求域名把不同客户映射到各自的静态站点。

## 固定页面

- `/`：客户档案上半部分原文 + 固定六项客户优势。
- `/enterprise/`：完整企业介绍、经营信息、资源与合作经验。
- `/products/`：完整产品与服务、重点线路、服务流程及询价信息。

模板统一位于 `layouts/`；客户站点资料位于 `data/sites/<site-key>.yaml`；三页内容位于 `content/<site-key>/`。新增客户不复制模板。

## 本地构建

```bash
hugo --source microsites --destination public --cleanDestinationDir --minify
python3 -m http.server 4311 --directory microsites/public/<site-key>
```

## 新增客户

1. 新增 `data/sites/<site-key>.yaml`，填写品牌、联系方式、来源链接与结构化企业信息。
2. 新增 `content/<site-key>/_index.md`、`enterprise.md`、`products.md`；首页必须配置六项优势，企业页与产品页完整承载客户确认的信息。
3. 在 `src/index.js` 的 `SITES` 中增加 `子域名 → siteKey` 映射。
4. 在 `wrangler.toml` 中为该子域名增加一条 `custom_domain = true` 的精确域名绑定。
5. 重新执行 Hugo 构建和 Wrangler 部署。

## 部署前提

每个客户子域名使用 Cloudflare Worker Custom Domain 绑定。Wrangler 会为精确域名创建 DNS 与证书，并把请求交给同一个多租户 Worker；无需建立多个 Pages 项目，也不会由通配路由误接管其他现有子域名。首个客户站已部署至 `https://guandu.goodbusiness.cloud/`。
