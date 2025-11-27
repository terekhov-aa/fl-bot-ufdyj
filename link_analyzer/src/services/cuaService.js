// FILE: link_analyzer/src/services/cuaService.js
const {Stagehand} = require('@browserbasehq/stagehand');
const ParsedPage = require('../models/ParsedPage');
const config = require('../config');
const logger = require('../utils/logger');

/**
 * @param {string} url
 * @param {object} options
 * @param {string} [options.contentType]
 * @param {object} [options.signals]
 */
async function runCUAForProjectInfo(url, options = {}) {
    const limitations = [];
    const errors = [];

    if (!config.cuaGloballyEnabled) {
        limitations.push('CUA is disabled via CUA_ENABLED/ENABLE_CUA');
        return {
            parsedPageFromCUA: null,
            projectInfoFromCUA: null,
            projectInfoText: null,
            limitations,
            errors,
        };
    }

    if (!config.browserbaseApiKey || !config.browserbaseProjectId) {
        limitations.push('Browserbase credentials missing for CUA');
        return {
            parsedPageFromCUA: null,
            projectInfoFromCUA: null,
            projectInfoText: null,
            limitations,
            errors,
        };
    }

    // жёстко ограничиваем шаги сверху 12 (а снизу не даём опуститься ниже 1)
    const maxSteps =
        Math.max(1, Math.min(Number(config.cuaMaxSteps || 12) || 12, 12));

    // грубая оценка лимита по символам под 4000 токенов
    const approxCharLimit =
        Number.isFinite(config.cuaMaxTokens) && config.cuaMaxTokens > 0
            ? config.cuaMaxTokens * 4
            : 16000;

    let parsedPageFromCUA = null;
    let projectInfoFromCUA = null;
    let projectInfoText = null;
    let stagehand;
    let rawMessage = ''; // сюда складываем всё, что успели получить от агента

    try {
        const cuaModel =
            config.cuaModel && config.cuaModel.trim().length > 0
                ? config.cuaModel.trim()
                : 'google/gemini-2.5-computer-use-preview-10-2025';

        logger.info('Launching Stagehand CUA', {
            model: cuaModel,
            signals: options.signals,
            maxSteps,
            maxTokensHint: config.cuaMaxTokens,
        });
        logger.info('==============================================================');
        logger.info(config.cuaApiKey);
        logger.info('==============================================================');

        stagehand = new Stagehand({
            env: 'BROWSERBASE',
            apiKey: config.browserbaseApiKey,
            projectId: config.browserbaseProjectId,
            model: {
                modelName: config.cuaModel || 'anthropic/claude-haiku-4-5-20251001',
                apiKey: config.cuaApiKey || process.env.ANTHROPIC_API_KEY,
            },
            browserbaseSessionCreateParams: {
                timeout: 600,
                browserSettings: {
                    viewport: {width: 1920, height: 1080},
                    blockAds: true,
                },
            },
        });

        await stagehand.init();

        const page =
            stagehand.page ||
            (stagehand.context &&
                stagehand.context.pages &&
                stagehand.context.pages()[0]);

        if (!page) {
            throw new Error('Stagehand page not available');
        }

        // сразу переходим на нужную страницу
        await page.goto(url, {waitUntil: 'networkidle'});

        const agentModel =
            config.cuaApiKey || config.cuaBaseUrl
                ? {
                    modelName: cuaModel,
                    apiKey: config.cuaApiKey || undefined,
                    baseURL: config.cuaBaseUrl || undefined,
                }
                : cuaModel;

        const agent = stagehand.agent({
            cua: true,
            model: agentModel,
            systemPrompt:
                'Ты специализированный ассистент, который управляет браузером для фрилансера.\n' +
                'У тебя очень ограниченный бюджет действий (порядка 10–12 шагов). Поэтому:\n' +
                '\n' +
                '• Работай только в рамках текущего ресурса (страницы или доски), не открывай другие сайты и вкладки.\n' +
                '• Используй минимум скроллов и кликов, чтобы получить общую картину: какая это система, из каких разделов состоит и что в каждом разделе.\n' +
                '• Избегай длинных многошаговых сценариев и углублённой навигации; цель — ширина обзора, а не подробности.\n' +
                '• Не описывай свои действия или процесс (“я увидел, я кликнул”), говори по существу.\n' +
                '• Говори по‑русски, даже если интерфейс на другом языке.\n' +
                '\n' +
                'Твоя задача — быстро составить целостное впечатление о продукте и рассказать о нём фрилансеру.\n',
        });

        const instruction =
            'Открой текущий ресурс (страницу, доску с экранами или сайт) и в несколько простых действий (несколько скроллов, выбор видимых разделов) собери максимальное представление о проекте:\n' +
            '\n' +
            '• Определи, что это за сервис или приложение, какую проблему он решает и для кого предназначен.\n' +
            '• Выдели основные разделы или пользовательские потоки (ввод/регистрация, основная функциональность, платежи, история, профиль и т. п.), не углубляясь в каждый экран.\n' +
            '• Прикинь, сколько разных групп экранов или шагов ты видишь и как они логически связаны.\n' +
            '• После короткого обзора остановись и сформируй **один насыщенный текстовый ответ** (без JSON) на русском языке.  \n' +
            '  В нём кратко опиши назначение продукта, основные сценарии использования и структуру интерфейса.  \n' +
            '  Избегай пустых фраз и описаний своих действий.\n' +
            '\n' +
            'Важно: не переходи на внешние сайты, не открывай длинные цепочки навигации. В ответе отрази общую картину, а не отдельную деталь.\n';

        const agentResult = await agent.execute({
            instruction,
            maxSteps,
            page,
            highlightCursor: false,
        });

        if (agentResult && typeof agentResult.message === 'string') {
            rawMessage = agentResult.message;
        }

        if (!agentResult || typeof agentResult !== 'object') {
            limitations.push('CUA agent returned unexpected result format');
        } else {
            if (agentResult.success === false) {
                limitations.push('CUA agent reported unsuccessful execution');
            }
            // completed === false может означать, что упёрлись в maxSteps
            if (agentResult.completed === false) {
                limitations.push('CUA agent stopped early (possibly hit maxSteps limit)');
            }

            const text = (agentResult.message || '').trim();

            if (!text) {
                limitations.push('CUA agent returned empty message');
            } else {
                const limitedText =
                    text.length > approxCharLimit
                        ? `${text.slice(0, approxCharLimit)}…`
                        : text;

                parsedPageFromCUA = new ParsedPage({
                    url,
                    title: (await page.title().catch(() => '')) || '',
                    description: '',
                    content: limitedText,
                    statusCode: 200,
                    contentLength: limitedText.length,
                });
                projectInfoText = limitedText;
            }
        }
    } catch (err) {
        // если что-то упало ПОСЛЕ того, как успели получить rawMessage — пробуем его сохранить
        if (!projectInfoText && rawMessage && typeof rawMessage === 'string') {
            const safeText =
                rawMessage.length > approxCharLimit
                    ? `${rawMessage.slice(0, approxCharLimit)}…`
                    : rawMessage.trim();

            if (safeText) {
                parsedPageFromCUA = new ParsedPage({
                    url,
                    title: '',
                    description: '',
                    content: safeText,
                    statusCode: 200,
                    contentLength: safeText.length,
                });
                projectInfoText = safeText;
                limitations.push(
                    'Stagehand CUA threw, but partial text from agent was recovered'
                );
            }
        }

        limitations.push('Stagehand CUA failed');
        errors.push(`CUA error: ${err.message}`);
        logger.error(`CUA error: ${err.message}`);
    } finally {
        if (stagehand) {
            try {
                await stagehand.close();
            } catch (closeError) {
                logger.error(`Failed to close Stagehand: ${closeError.message}`);
            }
        }
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
    runCUAForProjectInfo,
};
