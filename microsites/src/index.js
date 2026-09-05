const SITES = {
  "guandu.goodbusiness.cloud": {
    siteKey: "guandu",
    canonicalUrl: "https://guandu.goodbusiness.cloud/",
    title: "武汉官渡国际货运代理有限公司",
    lastmod: "2026-09-05",
  },
  "qingyan.goodbusiness.cloud": {
    siteKey: "qingyan",
    canonicalUrl: "https://qingyan.goodbusiness.cloud/",
    title: "清颜美舍",
    lastmod: "2026-09-06",
  },
};

const PREVIEW_HOSTS = new Set(["127.0.0.1", "localhost"]);

function withSharedHeaders(response) {
  const headers = new Headers(response.headers);
  headers.set("Cache-Control", "public, max-age=300, s-maxage=3600");
  headers.set("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; upgrade-insecure-requests");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  return new Response(response.body, { status: response.status, headers });
}

function textResponse(body, contentType, status = 200) {
  return withSharedHeaders(new Response(body, {
    status,
    headers: { "Content-Type": `${contentType}; charset=utf-8` },
  }));
}

function notFound(hostname) {
  const escapedHost = hostname.replace(/[&<>"']/g, "");
  return textResponse(
    `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>站点未配置</title><style>body{margin:0;display:grid;place-items:center;min-height:100vh;background:#111918;color:#f3eee4;font:16px/1.7 -apple-system,"PingFang SC",sans-serif}main{max-width:36rem;padding:2rem}p{color:#aeb8b3}code{color:#ff7a45}</style><main><h1>这个子站尚未配置</h1><p><code>${escapedHost}</code> 还没有对应的客户页面。</p></main></html>`,
    "text/html",
    404,
  );
}

export default {
  async fetch(request, env) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return textResponse("Method Not Allowed", "text/plain", 405);
    }

    const url = new URL(request.url);
    const hostname = url.hostname.toLowerCase().replace(/\.$/, "");
    const site = SITES[hostname] || (PREVIEW_HOSTS.has(hostname) ? SITES["guandu.goodbusiness.cloud"] : null);

    if (!site) {
      return notFound(hostname);
    }

    if (url.pathname === "/robots.txt") {
      return textResponse(`User-agent: *\nAllow: /\nSitemap: ${site.canonicalUrl}sitemap.xml\n`, "text/plain");
    }

    if (url.pathname === "/sitemap.xml") {
      const urls = ["", "enterprise/", "products/"]
        .map((path) => `<url><loc>${site.canonicalUrl}${path}</loc><lastmod>${site.lastmod}</lastmod></url>`)
        .join("");
      const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}</urlset>`;
      return textResponse(xml, "application/xml");
    }

    if (url.pathname === "/index.html") {
      return withSharedHeaders(Response.redirect(site.canonicalUrl, 308));
    }

    if (url.pathname === "/enterprise" || url.pathname === "/products") {
      return withSharedHeaders(Response.redirect(`${site.canonicalUrl}${url.pathname.slice(1)}/`, 308));
    }

    const pageMap = {
      "/": "index.html",
      "/enterprise/": "enterprise/index.html",
      "/products/": "products/index.html",
    };
    const pagePath = pageMap[url.pathname];

    if (!pagePath) {
      return notFound(hostname);
    }

    const assetUrl = new URL(request.url);
    assetUrl.pathname = `/${site.siteKey}/${pagePath}`;
    assetUrl.search = "";
    const assetResponse = await env.ASSETS.fetch(new Request(assetUrl, request));
    return withSharedHeaders(assetResponse);
  },
};
