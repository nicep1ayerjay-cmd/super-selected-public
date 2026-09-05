import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.dirname(fileURLToPath(import.meta.url));
const read = (file) => readFileSync(path.join(root, file), 'utf8');
const decode = (value) => value.replace(/&#(x[0-9a-f]+|\d+);/gi, (_, n) => String.fromCodePoint(n[0].toLowerCase() === 'x' ? parseInt(n.slice(1), 16) : Number(n)))
  .replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&amp;/g, '&');
const text = (html) => decode(html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, '').replace(/<[^>]+>/g, '')).replace(/\s+/g, '');
const tagContent = (html, pattern, label) => {
  const value = html.match(pattern)?.[1];
  assert(value, `缺少 ${label}`);
  return decode(value);
};
const companyKeys = ['companyName', 'productService', 'brandStory', 'trustEndorsement', 'trustEndorsementUrl'];
const productKeys = ['name', 'features', 'audience', 'differentiators', 'problems', 'scenes', 'proof'];
const internal = /原始字段|已核验补充|表述边界|固定六项结构|不得表述|不表述为|不能承诺|不能说|资料明确记载/;
const seenDescriptions = new Set();
const sourceFiles = readdirSync(path.join(root, 'data/customer_sources')).filter((name) => name.endsWith('.json'));
assert(sourceFiles.length, '缺少客户资料');
const siteKeys = readdirSync(path.join(root, 'data/sites')).filter((name) => /\.(yaml|yml|json)$/.test(name)).map((name) => name.replace(/\.(yaml|yml|json)$/, ''));
assert.deepEqual(sourceFiles.map((name) => name.slice(0, -5)).sort(), siteKeys.sort(), '每个客户必须有对应的完整资料');

for (const file of sourceFiles) {
  const key = file.slice(0, -5);
  const source = JSON.parse(read(`data/customer_sources/${file}`));
  const { fields, products } = source.knowledgePayload;
  assert(products.length, `${key}: 缺少产品`);
  for (const field of Object.keys(fields)) assert([...companyKeys, 'otherInfo'].includes(field), `${key}: 企业新字段 ${field} 尚未映射`);
  for (const product of products) for (const field of Object.keys(product)) assert([...productKeys, 'id', 'forbidden'].includes(field), `${key}: 产品新字段 ${field} 尚未映射`);
  const pages = Object.fromEntries(['', 'enterprise/', 'products/'].map((route) => [route, read(`public/${key}/${route}index.html`)]));
  for (const [route, html] of Object.entries(pages)) {
    assert(!internal.test(text(html)), `${key}/${route}: 出现工程说明`);
    assert.equal((html.match(/<h1(?:\s|>)/g) || []).length, 1, `${key}/${route}: H1 数量异常`);
    assert(!html.includes('microsites.invalid'), `${key}/${route}: 存在占位域名`);
    const title = tagContent(html, /<title>([^<]+)<\/title>/, `${key}/${route} title`);
    const description = tagContent(html, /<meta name=description content="([^"]+)"/, `${key}/${route} description`);
    const robots = tagContent(html, /<meta name=robots content="([^"]+)"/, `${key}/${route} robots`);
    const canonical = tagContent(html, /<link rel=canonical href="?([^"\s>]+)"?/, `${key}/${route} canonical`);
    assert.equal(tagContent(html, /<meta property="og:title" content="([^"]+)"/, `${key}/${route} og:title`), title, `${key}/${route}: OG 标题未使用页面完整标题`);
    assert.equal(tagContent(html, /<meta property="og:description" content="([^"]+)"/, `${key}/${route} og:description`), description, `${key}/${route}: OG 描述与页面描述不一致`);
    assert.equal(tagContent(html, /<meta property="og:url" content="([^"]+)"/, `${key}/${route} og:url`), canonical, `${key}/${route}: OG URL 与 canonical 不一致`);
    assert.equal(tagContent(html, /<meta name=twitter:title content="([^"]+)"/, `${key}/${route} twitter:title`), title, `${key}/${route}: Twitter 标题未使用页面完整标题`);
    assert.equal(tagContent(html, /<meta name=twitter:description content="([^"]+)"/, `${key}/${route} twitter:description`), description, `${key}/${route}: Twitter 描述与页面描述不一致`);
    assert.equal(robots, 'index,follow,max-image-preview:large', `${key}/${route}: 页面未向爬虫完全开放`);
    assert(canonical.startsWith(`https://${key}.goodbusiness.cloud/`), `${key}/${route}: canonical 未指向本客户域名`);
    assert(title.includes(fields.companyName), `${key}/${route}: 页面标题未包含客户名`);
    assert(!seenDescriptions.has(description), `${key}/${route}: 元描述与其他页面重复`);
    seenDescriptions.add(description);
    const schema = JSON.parse(tagContent(html, /<script type=application\/ld\+json>([\s\S]*?)<\/script>/, `${key}/${route} structured data`));
    assert.equal(schema['@type'], route ? 'WebPage' : 'Organization', `${key}/${route}: 结构化数据类型不准确`);
    assert.equal(schema.name, route ? title : fields.companyName, `${key}/${route}: 结构化数据名称不准确`);
    assert.equal(schema.url, canonical, `${key}/${route}: 结构化数据 URL 与 canonical 不一致`);
    assert.equal(schema.description, description, `${key}/${route}: 结构化数据描述与页面描述不一致`);
  }
  for (const field of companyKeys) {
    if (!fields[field]) continue;
    for (const route of ['', 'enterprise/']) assert(text(pages[route]).includes(fields[field].replace(/\s+/g, '')), `${key}/${route}: 企业字段 ${field} 未全文保留`);
  }
  for (const [index, product] of products.entries()) for (const field of productKeys) {
    if (!product[field]) continue;
    assert(text(pages['products/']).includes(product[field].replace(/\s+/g, '')), `${key}/products: 产品 ${index + 1} 字段 ${field} 未全文保留`);
  }
  const companyArticle = pages['enterprise/'].match(/<div class=["']?prose["']?>([\s\S]*?)<\/div><\/article>/)?.[1];
  const homeArticle = pages[''].match(/<article class=["']?prose["']?>([\s\S]*?)<\/article>/)?.[1];
  assert(companyArticle && homeArticle, `${key}: 找不到企业正文`);
  assert(text(homeArticle).includes(text(companyArticle)), `${key}: 首页未保留完整企业正文`);
  const expected = read(`content/${key}/_index.md`).match(/^  - title:/gm)?.length || 0;
  assert(expected > 0, `${key}: 缺少优势`);
  assert.equal((pages[''].match(/<article class=["']?advantage["']?>/g) || []).length, expected, `${key}: 优势未完整渲染`);
  console.log(`${key}: 企业 ${companyKeys.filter((field) => fields[field]).length} 个字段、产品 ${products.length} 组完整字段、首页企业全文、${expected} 项优势、三页结构与文案检查通过。`);
}

// The original profile's first four sections contain the public identity,
// contact, service and operating information required on the example home.
if (siteKeys.includes('guandu')) {
  const original = read('../content/recommendations/wuhan-guandu-logistics/object-profile.md');
  const profile = original.slice(original.indexOf('## 一、'), original.indexOf('## 五、'));
  const expected = profile.split('\n').filter((line) => line.trim() && !line.startsWith('#')).map((line) => line
    .replace(/^\s*-\s*/, '').replace(/\*\*[^*]+\*\*\s*/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/^(月吞吐量|年营业额|自有资源)：\s*/, '').trim()).filter(Boolean);
  const home = text(read('public/guandu/index.html'));
  for (const value of expected) assert(home.includes(value.replace(/\s+/g, '')), `guandu: 原档案内容缺失：${value}`);
  console.log(`guandu: 原档案前四节 ${expected.length} 条内容逐项通过。`);
}
