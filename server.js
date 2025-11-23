const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');

class ProjectInfo {
  constructor() {
    this.projectType = "";
    this.summary = "";
    this.targetAudience = "";
    this.mainFlows = [];
    this.mainFeatures = [];
    this.techStackGuess = [];
    this.complexity = "unknown";
    this.risks = [];
    this.tasksForFreelancer = [];
  }
}

function detectContentType(rawUrl) {
  try {
    const url = new URL(rawUrl);
    const hostname = url.hostname.toLowerCase();
    const pathname = url.pathname || "";

    if (hostname.includes("docs.google.com") && pathname.includes("/document/")) {
      return "google_doc";
    }
    if (hostname.includes("notion.so") || hostname.endsWith(".notion.site")) {
      return "notion";
    }
    if ((hostname.includes("atlassian.net") && pathname.includes("/wiki")) || pathname.includes("/pages/viewpage.action")) {
      return "confluence";
    }
    if (hostname.includes("figma.com") && pathname.includes("/file/")) {
      return "figma";
    }
    if (hostname.includes("youtube.com") && pathname.includes("/watch")) {
      return "youtube";
    }
    if (hostname === "youtu.be") {
      return "youtube";
    }
    if (hostname.includes("github.com") || hostname.includes("gitlab.com") || hostname.includes("bitbucket.org")) {
      return "github";
    }
    return "web_page";
  } catch (err) {
    return "web_page";
  }
}

function normalizeWhitespace(text) {
  if (!text) return "";
  return text.replace(/\s+/g, " ").trim();
}

function truncateText(text, limit = 20000) {
  if (!text) return text;
  if (text.length <= limit) return text;
  return text.slice(0, limit);
}

function stripHtmlToText(html) {
  const $ = cheerio.load(html || "");
  $("script, style, noscript").remove();
  $('*').contents().each(function () {
    if (this.type === 'comment') {
      $(this).remove();
    }
  });
  const bodyText = $("body").text();
  return normalizeWhitespace(bodyText);
}

function parseHtmlDocument(html, rawUrl, contentType, limitations) {
  const $ = cheerio.load(html || "");
  $("script, style, noscript").remove();
  $('*').contents().each(function () {
    if (this.type === 'comment') {
      $(this).remove();
    }
  });

  let title = normalizeWhitespace($("title").first().text()) || null;
  let description = normalizeWhitespace($('meta[name="description"]').attr('content')) || null;
  let mainHeading = normalizeWhitespace($("h1").first().text()) || null;
  if (!mainHeading) {
    mainHeading = normalizeWhitespace($("h2").first().text()) || null;
  }

  const sectionHeadings = [];
  $("h2, h3").each((_, el) => {
    if (sectionHeadings.length >= 30) return;
    const text = normalizeWhitespace($(el).text());
    if (text) sectionHeadings.push(text);
  });

  let contentText = normalizeWhitespace($("body").text());
  contentText = truncateText(contentText);

  if (!description && contentText) {
    description = truncateText(contentText, 500);
  }

  if (contentType === "youtube") {
    if (title && title.endsWith(" - YouTube")) {
      title = title.replace(/ - YouTube$/, "");
    }
    const match = html.match(/"shortDescription":"(.*?)"/s);
    if (match && match[1]) {
      const rawDesc = match[1];
      const cleaned = rawDesc.replace(/\\n/g, "\n").replace(/\\"/g, '"');
      description = description || cleaned;
      contentText = truncateText(`${cleaned}\n\n${contentText || ""}`);
    }
  }

  if (contentType === "github") {
    const readmeText = normalizeWhitespace($("#readme").text()) || normalizeWhitespace($("article.markdown-body").text());
    if (readmeText) {
      contentText = truncateText(readmeText);
    }
  }

  if ((contentType === "notion" || contentType === "confluence") && (!contentText || contentText.length < 200)) {
    const extraBits = [];
    $('[aria-label], [alt]').each((_, el) => {
      const val = normalizeWhitespace($(el).attr('aria-label') || $(el).attr('alt'));
      if (val) extraBits.push(val);
    });
    if (extraBits.length) {
      contentText = truncateText(`${contentText || ""}\n${extraBits.join('\n')}`);
    }
    if (!contentText || contentText.length < 50) {
      limitations.push("doc_viewer");
    }
  }

  if (contentType === "figma") {
    limitations.push("figma_readonly");
  }

  return {
    url: rawUrl,
    contentType,
    title,
    description,
    mainHeading,
    sectionHeadings,
    content: contentText || null,
  };
}

async function cheapParse(rawUrl, contentType, limitations) {
  if (contentType === "google_doc") {
    return cheapParseGoogleDoc(rawUrl, limitations);
  }

  const parsed = {
    url: rawUrl,
    contentType,
    title: null,
    description: null,
    mainHeading: null,
    sectionHeadings: [],
    content: null,
  };

  let response;
  try {
    response = await axios.get(rawUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
      },
      timeout: 20000,
      validateStatus: () => true,
    });
  } catch (err) {
    limitations.push("http_error");
    return parsed;
  }

  const status = response.status;
  if (status === 401 || status === 403) {
    limitations.push("auth_required");
    return parsed;
  }
  if (status === 404) {
    limitations.push("http_404");
    return parsed;
  }
  if (status >= 500) {
    limitations.push("http_5xx");
    return parsed;
  }
  if (status >= 300) {
    limitations.push("http_error");
    return parsed;
  }

  const parsedHtml = parseHtmlDocument(response.data, rawUrl, contentType, limitations);
  return { ...parsed, ...parsedHtml };
}

async function cheapParseGoogleDoc(rawUrl, limitations) {
  const parsed = {
    url: rawUrl,
    contentType: "google_doc",
    title: null,
    description: null,
    mainHeading: null,
    sectionHeadings: [],
    content: null,
  };

  let documentId = null;
  try {
    const url = new URL(rawUrl);
    const parts = url.pathname.split("/").filter(Boolean);
    const idIndex = parts.indexOf("d");
    if (idIndex !== -1 && parts[idIndex + 1]) {
      documentId = parts[idIndex + 1];
    }
  } catch (err) {
    documentId = null;
  }

  if (!documentId) {
    limitations.push("google_doc_content_unavailable");
    return parsed;
  }

  const variants = [
    `https://docs.google.com/document/d/${documentId}/export?format=txt`,
    `https://docs.google.com/document/d/${documentId}/export?format=html`,
    `https://docs.google.com/document/d/${documentId}/mobilebasic`,
  ];

  let textContent = "";
  for (const endpoint of variants) {
    try {
      const resp = await axios.get(endpoint, {
        timeout: 15000,
        responseType: "text",
        validateStatus: () => true,
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
        },
      });
      if (resp.status === 401 || resp.status === 403) {
        continue;
      }
      if (resp.status >= 400) {
        continue;
      }
      if (endpoint.includes("format=txt")) {
        textContent = resp.data;
      } else {
        textContent = stripHtmlToText(resp.data);
      }
      if (normalizeWhitespace(textContent).length > 0) {
        break;
      }
    } catch (err) {
      continue;
    }
  }

  const cleaned = normalizeWhitespace(textContent);
  if (!cleaned || cleaned.length < 10) {
    limitations.push("auth_required");
    limitations.push("google_doc_content_unavailable");
    return parsed;
  }

  const lines = cleaned.split(/\n+/).map((l) => l.trim()).filter(Boolean);
  const title = lines.length ? lines[0] : null;
  const sectionHeadings = lines.slice(1, 31);
  const content = truncateText(cleaned);
  const description = truncateText(cleaned, 500);

  return {
    ...parsed,
    title,
    mainHeading: title,
    sectionHeadings,
    description,
    content,
  };
}

async function tryProjectInfoExtraction(parsedContent) {
  if (!process.env.LLM_API_KEY || !process.env.LLM_MODEL) {
    return null;
  }
  if (!parsedContent || parsedContent.length < 200) {
    return null;
  }

  const trimmedContent = truncateText(parsedContent, 8000);
  const messages = [
    {
      role: "system",
      content:
        "You are an assistant that summarizes product briefs for freelance developers. Return only JSON for the ProjectInfo schema without extra text or hallucinations.",
    },
    {
      role: "user",
      content: `Extract ProjectInfo from the following content. Ensure all fields exist.\n${trimmedContent}`,
    },
  ];

  const baseUrl = (process.env.LLM_BASE_URL || "https://api.openai.com/v1").replace(/\/$/, "");

  try {
    const resp = await axios.post(
      `${baseUrl}/chat/completions`,
      {
        model: process.env.LLM_MODEL,
        messages,
        temperature: 0,
        response_format: { type: "json_object" },
      },
      {
        timeout: 30000,
        headers: {
          Authorization: `Bearer ${process.env.LLM_API_KEY}`,
          "Content-Type": "application/json",
        },
      }
    );

    const choice = resp.data && resp.data.choices && resp.data.choices[0];
    const content = choice && choice.message && choice.message.content;
    if (!content) return null;
    const parsed = JSON.parse(content);
    const info = new ProjectInfo();
    Object.keys(info).forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(parsed, key)) {
        info[key] = parsed[key];
      }
    });
    return info;
  } catch (err) {
    return null;
  }
}

async function analyzeUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== "string") {
    throw new Error("Invalid URL");
  }

  const limitations = [];
  const contentType = detectContentType(rawUrl);

  let parsed = await cheapParse(rawUrl, contentType, limitations);
  let projectInfo = null;
  let analysisMode = "parse";

  projectInfo = await tryProjectInfoExtraction(parsed.content);
  if (projectInfo) {
    analysisMode = "extract";
  }

  const enableCua = String(process.env.ENABLE_CUA || "true").toLowerCase() !== "false";
  const needsCua =
    enableCua &&
    !projectInfo &&
    contentType === "web_page" &&
    (!parsed.content || parsed.content.length < 200) &&
    !limitations.includes("auth_required") &&
    !limitations.includes("google_doc_content_unavailable");

  if (needsCua) {
    analysisMode = "cua";
    let browser;
    try {
      const puppeteer = require("puppeteer");
      browser = await puppeteer.launch({ headless: true });
      const page = await browser.newPage();
      await page.goto(rawUrl, { waitUntil: "networkidle2", timeout: 30000 });
      const html = await page.content();
      parsed = parseHtmlDocument(html, rawUrl, contentType, limitations);
      if (parsed.content && parsed.content.length >= 200) {
        projectInfo = await tryProjectInfoExtraction(parsed.content);
        if (projectInfo && analysisMode !== "extract") {
          analysisMode = "extract";
        }
      }
    } catch (err) {
      limitations.push("cua_failed");
    } finally {
      if (browser) {
        try {
          await browser.close();
        } catch (err) {
          // ignore
        }
      }
    }
  }

  return {
    url: rawUrl,
    contentType,
    parsed,
    projectInfo,
    analysisMode,
    limitations,
  };
}

const app = express();
app.use(express.json());

app.post("/analyze", async (req, res) => {
  const { url } = req.body || {};
  if (!url || typeof url !== "string") {
    return res.status(400).json({ success: false, error: "url must be a non-empty string" });
  }
  try {
    const result = await analyzeUrl(url);
    return res.json({ success: true, data: result });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message || "Unknown error" });
  }
});

const port = parseInt(process.env.PORT || "3000", 10);
app.listen(port, () => {
  console.log("Link analyzer listening on port", port);
});

module.exports = { analyzeUrl, detectContentType, ProjectInfo };
