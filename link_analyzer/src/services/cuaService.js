// FILE: link_analyzer/src/services/cuaService.js
const puppeteer = require('puppeteer');
const { Stagehand } = require('@browserbasehq/stagehand');
const { z } = require('zod');

const ParsedPage = require('../models/ParsedPage');
const ProjectInfo = require('../models/ProjectInfo');
const { extractTextFromHtml } = require('./htmlParser');
const config = require('../config');
const logger = require('../utils/logger');

async function renderWithPuppeteer(rawUrl) {
  let browser;
  try {
    browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    const page = await browser.newPage();
    await page.goto(rawUrl, { waitUntil: 'networkidle2', timeout: 20000 });
    const html = await page.content();
    return html;
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

async function analyzeWithCua(rawUrl, contentType, limitations = []) {
  if (!config.cuaGloballyEnabled) {
    limitations.push('CUA disabled');
    return { parsed: null, used: false };
  }
  try {
    const html = await renderWithPuppeteer(rawUrl);
    const meta = extractTextFromHtml(html);
    const parsed = new ParsedPage({ url: rawUrl, title: meta.title, description: meta.description, content: meta.content });
    return { parsed, used: true };
  } catch (error) {
    logger.error(`CUA analysis failed: ${error.message}`);
    limitations.push('CUA failed');
    return { parsed: null, used: true };
  }
}

/**
 * @param {string} url
 * @param {object} options
 * @param {string} [options.contentType]
 * @param {object} [options.signals]
 */
async function runCUAForProjectInfo(url, options = {}) {
  let parsedPageFromCUA = null;
  let projectInfoFromCUA = null;
  let projectInfoText = null;
  const limitations = [];
  const errors = [];

  if (!config.cuaGloballyEnabled) {
    limitations.push('CUA is disabled via CUA_ENABLED/ENABLE_CUA');
    return { parsedPageFromCUA: null, projectInfoFromCUA: null, projectInfoText: null, limitations, errors };
  }

  try {
    const hasBrowserbaseConfig =
      config.useBrowserbaseForCua &&
      config.browserbaseApiKey &&
      config.browserbaseProjectId;

    if (hasBrowserbaseConfig) {
      logger.info('Starting CUA via Browserbase Stagehand', {
        url,
        contentType: options.contentType,
        signals: options.signals,
      });

      let stagehand;
      try {
        const model = config.cuaModel || 'anthropic/claude-haiku-4-5-20251001';

        let modelApiKey = null;
        if (model.startsWith('anthropic/')) {
          modelApiKey = process.env.ANTHROPIC_API_KEY || config.cuaApiKey || config.llmApiKey;
        } else if (model.startsWith('openai/')) {
          modelApiKey = process.env.OPENAI_API_KEY || config.llmApiKey || config.cuaApiKey;
        }

        if (!modelApiKey) {
          throw new Error(`CUA modelApiKey is not configured for model ${model}`);
        }

        stagehand = new Stagehand({
          env: 'BROWSERBASE',
          apiKey: config.browserbaseApiKey,
          projectId: config.browserbaseProjectId,
          model,
          modelApiKey,
          verbose: 0,
        });

        await stagehand.init();

        const page = stagehand.context.activePage();
        if (!page) {
          throw new Error('Stagehand: no active page context');
        }

        await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });

        try {
          await page.waitForTimeout(2000);
          await page.evaluate(() => {
            window.scrollTo(0, document.body.scrollHeight);
          });
          await page.waitForTimeout(1000);
        } catch (e) {
          logger.warn('CUA scroll evaluation warning', { message: e.message });
        }

        try {
          const html = await page.content();
          const meta = extractTextFromHtml(html);
          parsedPageFromCUA = new ParsedPage({
            url,
            title: meta.title,
            description: meta.description,
            content: meta.content,
            statusCode: 200,
            contentLength: meta.content ? meta.content.length : null,
          });
        } catch (e) {
          limitations.push('Failed to build ParsedPage from CUA HTML');
          logger.warn('CUA HTML -> ParsedPage failed', { message: e.message });
        }

        const schema = z.object({
          projectType: z.string().optional(),
          summary: z.string().optional(),
          targetAudience: z.string().optional(),
          mainFlows: z.array(z.string()).optional(),
          mainFeatures: z.array(z.string()).optional(),
          techStackGuess: z.array(z.string()).optional(),
          complexity: z.string().optional(),
          risks: z.array(z.string()).optional(),
          tasksForFreelancer: z.array(z.string()).optional(),
        });

        let agentResult = null;
        try {
          const createAgent = stagehand.createAgent || stagehand.agent;
          if (!createAgent) {
            throw new Error('Stagehand agent API not available');
          }

          const agent = await createAgent.call(stagehand, {
            instructions:
              'Изучи продукт на этой странице. Определи тип проекта/продукта, основную ценность, аудиторию, ключевые сценарии и функционал, риски и задачи, которые можно отдать фрилансеру. Верни JSON со схемой ProjectInfo (projectType, summary, targetAudience, mainFlows, mainFeatures, techStackGuess, complexity, risks, tasksForFreelancer). Если не удается структурировать, верни краткий текстовый вывод.',
            outputSchema: schema,
          });

          agentResult = await agent.run();
        } catch (e) {
          limitations.push('Stagehand agent failed');
          errors.push(`Browserbase CUA agent error: ${e.message}`);
        }

        if (!agentResult) {
          try {
            const extracted = await stagehand.extract(
              'Проанализируй этот интерфейс как проект для фрилансера и заполни все поля схемы: projectType, summary, targetAudience, mainFlows, mainFeatures, techStackGuess, complexity (low/medium/high/unknown), risks, tasksForFreelancer.',
              schema
            );
            agentResult = extracted;
          } catch (e) {
            limitations.push('Stagehand extract failed');
            errors.push(`Browserbase CUA extract error: ${e.message}`);
          }
        }

        if (agentResult && typeof agentResult === 'object' && !Array.isArray(agentResult)) {
          const mapped = new ProjectInfo();
          mapped.projectType = agentResult.projectType || '';
          mapped.summary = agentResult.summary || '';
          mapped.targetAudience = agentResult.targetAudience || '';
          mapped.mainFlows = Array.isArray(agentResult.mainFlows) ? agentResult.mainFlows : [];
          mapped.mainFeatures = Array.isArray(agentResult.mainFeatures) ? agentResult.mainFeatures : [];
          mapped.techStackGuess = Array.isArray(agentResult.techStackGuess) ? agentResult.techStackGuess : [];
          mapped.complexity = agentResult.complexity || 'unknown';
          mapped.risks = Array.isArray(agentResult.risks) ? agentResult.risks : [];
          mapped.tasksForFreelancer = Array.isArray(agentResult.tasksForFreelancer)
            ? agentResult.tasksForFreelancer
            : [];
          projectInfoFromCUA = mapped;
        } else if (agentResult && typeof agentResult === 'string') {
          projectInfoText = agentResult;
        }
      } catch (error) {
        errors.push(`Browserbase CUA error: ${error.message}`);
        limitations.push('Browserbase CUA failed, will try Puppeteer fallback if enabled');
      } finally {
        if (stagehand) {
          try {
            await stagehand.close();
          } catch (e) {
            logger.warn('Stagehand close warning', { message: e.message });
          }
        }
      }
    } else {
      limitations.push('Browserbase CUA not fully configured; set BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID');
    }

    if (!parsedPageFromCUA && config.cuaGloballyEnabled) {
      try {
        const html = await renderWithPuppeteer(url);
        const meta = extractTextFromHtml(html);
        parsedPageFromCUA = new ParsedPage({
          url,
          title: meta.title,
          description: meta.description,
          content: meta.content,
        });
      } catch (err) {
        limitations.push('Puppeteer fallback failed');
        errors.push(`CUA error: ${err.message}`);
      }
    }
  } catch (error) {
    errors.push(`CUA error: ${error.message || String(error)}`);
  }

  return {
    parsedPageFromCUA: parsedPageFromCUA || null,
    projectInfoFromCUA: projectInfoFromCUA || null,
    projectInfoText: projectInfoText || null,
    limitations,
    errors,
  };
}

module.exports = {
  analyzeWithCua,
  runCUAForProjectInfo,
};
