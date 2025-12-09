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
                'Ты специализированный ассистент-аналитик интерфейсов, который управляет браузером для фрилансера (дизайнера/верстальщика/разработчика).\n' +
                '\n' +
                'У тебя очень ограниченный бюджет действий (примерно 10–12 шагов). Поэтому:\n' +
                '\n' +
                '• Работай только в рамках текущего ресурса (страницы, лендинга, веб-сервиса, доски с макетами в Figma/Stitch и т.п.), не открывай другие сайты и вкладки.\n' +
                '• Используй минимум скроллов и кликов, чтобы получить общую картину: что это за продукт, какие есть типовые экраны/блоки и как они связаны.\n' +
                '• Избегай длинных многошаговых сценариев и глубокой навигации; цель — широкий обзор, а не пиксель-перфект разбор.\n' +
                '• Не описывай свои действия (“я кликнул”, “я пролистал”), говори только по сути результата.\n' +
                '• Всегда отвечай по-русски, даже если интерфейс на другом языке.\n' +
                '• Не выдумывай того, чего не видишь в интерфейсе. Если чего-то не хватает (нет мобильной версии, не видно футера и т.п.), честно напиши об этом.\n' +
                '\n' +
                'Твоя общая задача — быстро понять, КАК устроен интерфейс (структура и визуальный стиль), ЧТО за продукт перед тобой и КАКИЕ задачи это ставит перед фрилансером.\n',
        });

        const instruction =
            'Проанализируй текущий ресурс (страницу, лендинг, веб-сервис или доску с экранами) в несколько простых действий (несколько скроллов, переключение видимых разделов/фреймов) и составь цельное представление о продукте.\n' +
            '\n' +
            'В ответе дай один насыщенный текст на русском языке по следующей структуре:\n' +
            '\n' +
            '1. Что за продукт и для кого\n' +
            '   • Одним–двумя предложениями опиши тип продукта (лендинг, личный кабинет, мобильное приложение, админка и т.п.).\n' +
            '   • Какая основная проблема/задача решается для пользователя и кто этот пользователь.\n' +
            '\n' +
            '2. Основные пользовательские сценарии и потоки\n' +
            '   • Перечисли 3–7 ключевых сценариев (например: регистрация, выбор тарифа, оформление заказа, оплата, отслеживание статуса и т.д.).\n' +
            '   • Опиши, какие шаги примерно проходит пользователь в каждом сценарии (без лишней детализации по каждому экрану).\n' +
            '\n' +
            '3. Структура интерфейса\n' +
            '   • Опиши, как организована навигация: шапка, меню, левый/правый сайдбар, футер, вкладки, хэдэры разделов.\n' +
            '   • Перечисли типовые блоки/шаблоны: карточки, списки, таблицы, формы, модалки, шаги мастера и т.п.\n' +
            '   • Если это доска с макетами — скажи, сколько примерно групп экранов/фреймов видно и как они логически связаны (цепочки шагов).\n' +
            '\n' +
            '4. Визуальный стиль и тон\n' +
            '   • Опиши общие визуальные характеристики: светлая/тёмная тема, «чистый/минималистичный» или «яркий/маркетинговый» стиль, наличие иллюстраций, иконок, фото.\n' +
            '   • Отметь особенности типографики (крупные заголовки, много/мало текста, акценты), цвета (основные акцентные цвета, контраст, нейтральные фоны).\n' +
            '\n' +
            '5. Степень проработки дизайна\n' +
            '   • Что выглядит уже продуманным и готовым к реализации (полные тексты, состояния, ховеры, разные статусы и т.п.).\n' +
            '   • Что похоже на заглушки / черновик (рыба-тексты, отсутствующие состояния, нет адаптива, нет ошибок/лоадеров).\n' +
            '   • Если видно только часть потока (например, только онбординг или только оплата) — явно упомяни, что это фрагмент продукта и какой именно.\n' +
            '\n' +
            '6. Возможные задачи для фрилансера\n' +
            '   • Сформулируй, какие задачи логично поставить исполнителю, исходя из увиденного: сверстать макеты, адаптив, доработать состояния, продумать пустые/ошибочные экраны, собрать дизайн-систему из повторяющихся паттернов и т.п.\n' +
            '   • Пиши в формате списка из 3–7 конкретных пунктов.\n' +
            '\n' +
            'Важно:\n' +
            '• Не пересказывай дословно текстовые описания из левой панели, а связывай их с тем, как это реализовано в интерфейсе.\n' +
            '• Не переходи на внешние сайты, не углубляйся в длинные ветки навигации.\n' +
            '• Лучше честно написать «этого не видно на макетах», чем придумывать детали.\n';

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
