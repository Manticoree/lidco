# Примеры конфигурации LLM-провайдеров

Готовые конфигурации для подключения разных LLM-провайдеров к LIDCO.

## Использование

Скопируйте нужный файл в `~/.lidco/llm_providers.yaml`:

```bash
# Windows
copy configs\examples\zai-coding-plan.yaml %USERPROFILE%\.lidco\llm_providers.yaml

# Linux / macOS
cp configs/examples/zai-coding-plan.yaml ~/.lidco/llm_providers.yaml
```

## Доступные конфигурации

| Файл | Описание |
|------|----------|
| `zai-coding-plan.yaml` | Z.AI Coding Plan (подписка $3/$15/$60 в мес.) |
| `zai-api.yaml` | Z.AI стандартный API (оплата по токенам) |

## Добавление своего примера

Создайте YAML-файл в этой папке по аналогии с существующими.
