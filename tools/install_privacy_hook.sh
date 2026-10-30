#!/usr/bin/env bash
# pre-commit в своём клоне ядра — коммит с нашими значениями (id, имена, слаги, адреса) не рождается.
# Список значений — открытым файлом ~/.config/mila/privacy.json (вне репо, 600); без него хук не проверяет (и честно пишет об этом).
set -e
cd "$(git rev-parse --show-toplevel)"
H=.git/hooks/pre-commit
cat > "$H" <<'HOOK'
#!/usr/bin/env bash
python3 "$(git rev-parse --show-toplevel)/tools/privacy_lint.py" --staged || { echo "коммит остановлен privacy-lint (не обходите --no-verify: уберите значение, пример — из tests/fixtures/fake_people.py; CI и Качество ловят то же по закрытому списку)"; exit 1; }
HOOK
chmod +x "$H"; echo "pre-commit privacy-lint поставлен: $H"
