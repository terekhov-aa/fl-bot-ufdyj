const puppeteer = require('puppeteer');
const ParsedPage = require('../models/ParsedPage');
const ProjectInfo = require('../models/ProjectInfo');
const { extractTextFromHtml } = require('./htmlParser');
const config = require('../config');
const { normalizeWhitespace, truncateText } = require('../utils/textUtils');
const logger = require('../utils/logger');

const MAX_BODY_TEXT = 12000;

function parseProjectInfoFromMessage(message) {
  if (!message) return null;
  try {
    const jsonMatch = message.match(/\{[\s\S]*\}/);
    const payload = jsonMatch ? jsonMatch[0] : message;
    const parsed = JSON.parse(payload);
    const projectInfo = new ProjectInfo();
    Object.assign(projectInfo, parsed);
    return projectInfo;
  } catch (error) {
    logger.warn(`Failed to parse ProjectInfo from agent response: ${error.message}`);
    return null;
  }
}

async function buildParsedPageFromPage(page, rawUrl) {
  try {
    const [title, bodyText] = await Promise.all([
      page.title().catch(() => ''),
      page.evaluate(() => document?.body?.innerText || document?.body?.textContent || '').catch(() => ''),
    ]);

    const normalized = normalizeWhitespace(bodyText);
    const truncated = truncateText(normalized, MAX_BODY_TEXT);
    return new ParsedPage({
      url: rawUrl,
      title: normalizeWhitespace(title) || rawUrl,
      description: '',
      content: truncated,
      textPreview: truncateText(truncated, 300),
    });
  } catch (error) {
    logger.warn(`Unable to extract text from Browserbase page: ${error.message}`);
    return null;
  }
}

async function analyzeWithBrowserbaseAgent(rawUrl, contentType, limitations) {
  if (!config.cuaEnabled) {
    limitations.push('CUA disabled');
    return { projectInfo: null, parsed: null, actions: [], used: false };
  }

  if (!config.useBrowserbaseForCua || !config.browserbaseApiKey || !config.browserbaseProjectId) {
    limitations.push('Browserbase not configured for CUA');
    return { projectInfo: null, parsed: null, actions: [], used: false };
  }

  if (!config.cuaApiKey || !config.cuaModel) {
    limitations.push('CUA model not configured');
    return { projectInfo: null, parsed: null, actions: [], used: false };
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

    const agent = stagehand.agent({
      cua: true,
      model: {
        modelName: config.cuaModel,
        apiKey: config.cuaApiKey,
        baseURL: config.cuaBaseUrl || undefined,
        maxTokens: config.cuaMaxTokens,
      },
      systemPrompt:
        'Ты — эксперт по анализу проектов для фриланс-разработчика. Используй минимум шагов, чтобы понять проект. ' +
        'Делай только нужные действия в браузере, избегай лишних переходов. В конце верни строго JSON со схемой ProjectInfo: ' +
        'projectType, summary, targetAudience, mainFlows (array), mainFeatures (array), techStackGuess (array), ' +
        'complexity (one of low/medium/high/unknown), risks (array), tasksForFreelancer (array). Ответ без пояснений.',
    });

    const instruction =
      'Открой страницу, при необходимости проскроль и перейди по 1-2 внутренним ссылкам, если это помогает понять проект. ' +
      'Фокус на получении информации о назначении сервиса/продукта, целевой аудитории и ключевых функциях. ' +
      'Если видишь дизайн (Figma, Miro и т.п.), опиши его как продукт. Верни только JSON ProjectInfo.';

    const agentResult = await agent.execute({ instruction, maxSteps: config.cuaMaxSteps });
    const message = agentResult?.message || agentResult?.response || '';
    const projectInfo = parseProjectInfoFromMessage(message);
    const parsed = await buildParsedPageFromPage(page, rawUrl);

    logger.info(
      `CUA agent completed for ${rawUrl} using model ${config.cuaModel} with ${
        agentResult?.actions ? agentResult.actions.length : 0
      } actions`,
    );

    return { projectInfo, parsed, actions: agentResult?.actions || [], used: true };
  } catch (error) {
    logger.error(`CUA agent failed for ${rawUrl}: ${error.message}`);
    limitations.push('CUA agent failed');
    return { projectInfo: null, parsed: null, actions: [], used: true };
  } finally {
    if (stagehand && stagehand.close) {
      try {
        await stagehand.close();
      } catch (closeError) {
        logger.warn(`Failed to close Stagehand session: ${closeError.message}`);
      }
    }
  }
}

async function analyzeWithPuppeteerFallback(rawUrl, limitations) {
  if (!config.enableCua) {
    return { parsed: null, used: false };
  }

  let browser;
  try {
    browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
    const page = await browser.newPage();
    await page.goto(rawUrl, { waitUntil: 'networkidle2', timeout: 20000 });
    const html = await page.content();
    const meta = extractTextFromHtml(html);
    const parsed = new ParsedPage({ url: rawUrl, title: meta.title, description: meta.description, content: meta.content });
    return { parsed, used: true };
  } catch (error) {
    logger.error(`CUA puppeteer fallback failed: ${error.message}`);
    limitations.push('CUA fallback failed');
    return { parsed: null, used: true };
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

async function analyzeWithCua(rawUrl, contentType, limitations = []) {
  const agentOutcome = await analyzeWithBrowserbaseAgent(rawUrl, contentType, limitations);
  if (agentOutcome.used) {
    return agentOutcome;
  }

  // Fall back to legacy puppeteer parsing when Browserbase/agent is unavailable.
  const fallback = await analyzeWithPuppeteerFallback(rawUrl, limitations);
  return { ...fallback, projectInfo: null, actions: [] };
}

module.exports = { analyzeWithCua };
