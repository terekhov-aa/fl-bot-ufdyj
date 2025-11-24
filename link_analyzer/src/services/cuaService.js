const puppeteer = require('puppeteer');
const ParsedPage = require('../models/ParsedPage');
const { extractTextFromHtml } = require('./htmlParser');
const config = require('../config');
const logger = require('../utils/logger');

function extractJsonFromText(text) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (err) {
    // continue
  }
  const match = text.match(/\{[\s\S]*\}/);
  if (match) {
    try {
      return JSON.parse(match[0]);
    } catch (err) {
      return null;
    }
  }
  return null;
}

async function buildParsedPageFromPage(page, rawUrl) {
  const html = await page.content();
  const meta = extractTextFromHtml(html);
  return new ParsedPage({
    url: rawUrl,
    title: meta.title,
    description: meta.description,
    content: meta.content,
    htmlLength: meta.htmlLength,
    textLength: meta.textLength,
    textDensity: meta.textDensity,
    canvasCount: meta.canvasCount,
    svgCount: meta.svgCount,
    inputControlCount: meta.inputControlCount,
    suspectedCanvasApp: meta.suspectedCanvasApp,
  });
}

async function analyzeWithBrowserbaseAgent(rawUrl, contentType, limitations) {
  if (!config.useBrowserbaseForCua || !config.browserbaseApiKey || !config.browserbaseProjectId || !config.cuaApiKey || !config.cuaModel) {
    return { parsed: null, projectInfo: null, actions: [], used: false };
  }

  let stagehand;
  try {
    const { Stagehand } = await import('@browserbasehq/stagehand');
    stagehand = new Stagehand({
      env: 'BROWSERBASE',
      apiKey: config.browserbaseApiKey,
      projectId: config.browserbaseProjectId,
      model: {
        modelName: config.cuaModel,
        apiKey: config.cuaApiKey,
        baseURL: config.cuaBaseUrl || undefined,
        maxTokens: config.cuaMaxTokens,
      },
    });

    await stagehand.init();

    const page =
      (stagehand.context.activePage && stagehand.context.activePage()) ||
      (stagehand.context.pages && stagehand.context.pages()[0]) ||
      (stagehand.context.newPage && (await stagehand.context.newPage()));

    if (!page) {
      throw new Error('Stagehand page unavailable');
    }

    await page.goto(rawUrl, { waitUntil: 'networkidle', timeoutMs: 45000 });

    const systemPrompt =
      'Ты — эксперт по анализу проектов для фриланс-разработчика. Твоя цель — понять, что за продукт перед тобой, какие цели и задачи пользователей, ключевые фичи, риски и возможные задания для исполнителя. Работай безопасно: не вводи произвольные данные, не совершай деструктивные действия. В финале верни строго JSON формата ProjectInfo без дополнительного текста.';

    const instruction =
      'Открой страницу, при необходимости проскроль и открой 1–2 панели или раздела, чтобы понять, что за продукт или проект перед тобой. Сконцентрируйся на функциональности и назначении. Верни только JSON со структурой ProjectInfo (projectType, summary, targetAudience, mainFlows, mainFeatures, techStackGuess, complexity, risks, tasksForFreelancer).';

    const agent = stagehand.agent({
      cua: true,
      model: {
        modelName: config.cuaModel,
        apiKey: config.cuaApiKey,
        baseURL: config.cuaBaseUrl || undefined,
        maxTokens: config.cuaMaxTokens,
      },
      systemPrompt,
    });

    const agentResult = await agent.execute({ instruction, maxSteps: config.cuaMaxSteps });

    const message = agentResult?.message || agentResult?.response || '';
    const projectInfo = extractJsonFromText(message);
    const parsed = await buildParsedPageFromPage(page, rawUrl);

    return { projectInfo, parsed, actions: agentResult?.actions || [], used: true };
  } catch (error) {
    logger.error(`Browserbase CUA failed: ${error.message}`);
    limitations.push('CUA agent failed');
    return { parsed: null, projectInfo: null, actions: [], used: true };
  } finally {
    if (stagehand && stagehand.close) {
      try {
        await stagehand.close();
      } catch (err) {
        // ignore
      }
    }
  }
}

async function analyzeWithPuppeteerFallback(rawUrl, limitations) {
  let browser;
  try {
    browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
    const page = await browser.newPage();
    await page.goto(rawUrl, { waitUntil: 'networkidle2', timeout: 20000 });
    const parsed = await buildParsedPageFromPage(page, rawUrl);
    return { parsed, used: true, actions: [], projectInfo: null };
  } catch (error) {
    logger.error(`CUA fallback failed: ${error.message}`);
    limitations.push('CUA failed');
    return { parsed: null, used: true, actions: [], projectInfo: null };
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

async function analyzeWithCua(rawUrl, contentType, limitations = []) {
  if (!config.cuaEnabled) {
    limitations.push('CUA disabled');
    return { parsed: null, projectInfo: null, actions: [], used: false };
  }

  const agentOutcome = await analyzeWithBrowserbaseAgent(rawUrl, contentType, limitations);
  if (agentOutcome.used) {
    return agentOutcome;
  }

  const fallback = await analyzeWithPuppeteerFallback(rawUrl, limitations);
  return { ...fallback, projectInfo: fallback.projectInfo, used: true };
}

module.exports = { analyzeWithCua };
