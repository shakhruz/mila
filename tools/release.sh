#!/usr/bin/env bash
# release.sh X.Y.Z [--no-tag] — выпуск версии ядра. НИЧЕГО не пушит: в конце печатает команду пуша.
#   1. дерево чистое, версия новее последней; в CHANGELOG.md есть раздел "## vX.Y.Z" с блоком «Для хозяина»/«For the owner»
#   2. тесты mila-update, frontmatter, comments — зелёные
#   3. release.json: version, tag, date → коммит «release vX.Y.Z»
#   4. тег vX.Y.Z: подписанный (git tag -s), если задан user.signingkey; иначе аннотированный БЕЗ подписи (печатается отметка)
# Канал canary = main; канал stable = теги vX.Y.Z (без -rc). Отзыв релиза: добавить тег в yanked.json на main.
set -eu
cd "$(cd "$(dirname "$0")/.." && pwd)"
V="${1:-}"; NOTAG="${2:-}"
[[ "$V" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "usage: tools/release.sh X.Y.Z [--no-tag]" >&2; exit 2; }
[ -z "$(git status --porcelain)" ] || { echo "дерево не чистое: закоммитьте или уберите правки" >&2; exit 1; }
git rev-parse "v$V" >/dev/null 2>&1 && { echo "тег v$V уже есть" >&2; exit 1; }
last="$(git tag -l 'v[0-9]*' | grep -Ev -- '-' | sort -V | tail -1 || true)"
if [ -n "$last" ] && [ "$(printf '%s\nv%s\n' "$last" "$V" | sort -V | tail -1)" != "v$V" ]; then echo "v$V не новее $last" >&2; exit 1; fi
python3 - "$V" <<'PY' || exit 1
import re, sys
v = sys.argv[1]; t = open("CHANGELOG.md", encoding="utf-8").read()
m = re.search(r"^## v%s(?:[ \t][^\n]*)?\n(.*?)(?=^## |\Z)" % re.escape(v), t, re.S | re.M)
if not m: sys.exit("в CHANGELOG.md нет раздела '## v%s'" % v)
if not re.search(r"Для хозяина|For the owner", m.group(1), re.I): sys.exit("в разделе v%s нет блока «Для хозяина»/«For the owner» (карточка «Что нового»)" % v)
PY
bash skills/mila-update/test_update.sh | tail -1 | grep -Eq 'итог ([0-9]+)/\1$' || { echo "test_update.sh не зелёный" >&2; exit 1; }
bash skills/mila-update/test_nightly.sh | tail -1 | grep -Eq 'итог ([0-9]+)/\1$' || { echo "test_nightly.sh не зелёный" >&2; exit 1; }
bash skills/mila-update/test_renamed.sh | tail -1 | grep -Eq 'итог ([0-9]+)/\1$' || { echo "test_renamed.sh не зелёный" >&2; exit 1; }
bash tests/run_all.sh >/dev/null || { echo "tests/run_all.sh: есть упавшие (bash tests/run_all.sh)" >&2; exit 1; }
python3 tools/check_frontmatter.py skills templates >/dev/null || { echo "frontmatter: есть ошибки" >&2; exit 1; }
python3 - "$V" <<'PY'
import json, sys, time
v = sys.argv[1]; p = "release.json"; m = json.load(open(p, encoding="utf-8"))
m.update({"version": v, "tag": "v" + v, "date": time.strftime("%Y-%m-%d"), "notes": "CHANGELOG.md - section v" + v})
json.dump(m, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2); open(p, "a").write("\n")
PY
git add release.json; git commit -qm "release v$V"
if [ "$NOTAG" = "--no-tag" ]; then echo "коммит release v$V создан, тег не ставлю (--no-tag)"; exit 0; fi
if [ -n "$(git config user.signingkey || true)" ]; then
  git tag -s "v$V" -m "Mila v$V"; echo "тег v$V подписан"
else
  git tag -a "v$V" -m "Mila v$V"; echo "ВНИМАНИЕ: тег v$V БЕЗ подписи (нет user.signingkey; gpg --gen-key + git config user.signingkey <id>)"
fi
echo "Пуш не выполнен. Когда готовы:  git push origin <ветка> && git push origin v$V"
