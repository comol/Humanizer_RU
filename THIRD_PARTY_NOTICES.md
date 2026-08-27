# Заимствования и лицензии

Проект собран из своих правил и чужого опыта. Ниже — что откуда взято и на каких условиях. Все четыре источника распространяются под MIT; их уведомления приведены полностью, как того требует лицензия.

## Что взято

| Источник | Что использовано | Где у нас |
|---|---|---|
| [smixs/humanizer-ru](https://github.com/smixs/humanizer-ru) | Идея трёхфазного процесса (аудит → правка по находкам → линт), реестр артефактов копипаста, регэкспы «не просто X, а Y», каскада смягчений, двоеточия-подводки, повтора глагола; структура справочника паттернов; формат eval-сценариев | `humanizer_ru/rules.py`, `humanizer_ru/linter.py`, `skills/humanizer-ru/SKILL.md`, `references/patterns.md`, `tests/fixtures/evals.json` |
| [Vladimir-Human/humanizer-ru](https://github.com/Vladimir-Human/humanizer-ru) | Реестр маркеров копипаста из чат-ботов (класс A), правило «лучше пропустить машинный текст, чем испортить живой», запрет дописывать факты, идея списка ложных срабатываний | `humanizer_ru/rules.py` (ARTIFACT_RULES), `SKILL.md` (факт-замок), `references/false-positives.md` |
| [ilyautov/humanizer-ru](https://github.com/ilyautov/humanizer-ru) | Метрики ритма (CV длин предложений), структуры (ровные абзацы, листикл, обрыв), морфологии (сущ./глаг., номинализации), жанровые исключения, сводная оценка 0–100 с полосами | `humanizer_ru/metrics.py`, `humanizer_ru/linter.py` (_score) |
| [beaverbeard/chukovsky](https://github.com/beaverbeard/chukovsky) | Принципы «объективное правлю — вкусовое предлагаю», «голос автора неприкосновенен», «минимальная достаточная правка»; жанровый режим до правки; парцелляция как дефект во всех жанрах; формат вывода с разделом «На решение автора» | `skills/humanizer-ru/SKILL.md`, `references/voice.md` |

Код не копировался блоками: регэкспы переписаны под другие уровни строгости (тире, вопросы, двоеточия и «не только… но и» дефектами не считаются), метрики реализованы без razdel. Тем не менее источники идей указаны, а их лицензии соблюдены.

Книги, на которые опираются каталог и голос: М. Ильяхов, Л. Сарычева «Пиши, сокращай»; К. Чуковский «Живой как жизнь»; Н. Галь «Слово живое и мёртвое».

## Уведомления MIT

### smixs/humanizer-ru

MIT License

Copyright (c) 2026 Serge Shima

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

### Vladimir-Human/humanizer-ru

MIT License

Copyright (c) 2026 Vladimir

(Текст разрешения — тот же, что выше.)

### ilyautov/humanizer-ru

MIT License

Copyright (c) 2026 Ilya Utov

(Текст разрешения — тот же, что выше.)

### beaverbeard/chukovsky

MIT License

Copyright (c) 2026 Rodion Scryabin (beaverbeard)

(Текст разрешения — тот же, что выше.)
