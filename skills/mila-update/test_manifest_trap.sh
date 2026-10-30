#!/usr/bin/env bash
# mila-update: манифест-ловушка (26.10, вердикт Качества). Песочница: HOME, CLAUDE_CONFIG_DIR, MILA_WORK во временной папке;
# ничего вне неё не трогает. Запуск: bash test_manifest_trap.sh [папка_с_update.py]
set -u
HERE="$(cd "$(dirname "${1:-$0}")" && pwd)"; [ -n "${1:-}" ] && HERE="$(cd "$1" && pwd)"
U="python3 $HERE/update.py"; ok=0; n=0
ALL_T=(); trap 'chmod -R u+w "${ALL_T[@]}" 2>/dev/null; rm -rf "${ALL_T[@]}"' EXIT   # песочницы не остаются в /tmp
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
fresh() {  # новая песочница: $T, релиз $T/rel с честным навыком и «чужим секретом» $T/secret.txt рядом
  T="$(mktemp -d)"; ALL_T+=("$T"); export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
  mkdir -p "$CLAUDE_CONFIG_DIR/skills" "$MILA_WORK" "$T/rel/skills/dobryj" "$T/elsewhere"
  printf -- '---\nname: dobryj\ndescription: тест\n---\nтело\n' > "$T/rel/skills/dobryj/SKILL.md"; echo "SECRET-VALUE" > "$T/secret.txt"
  echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
}
rel() {  # rel '<зоны json>'
  printf '{"version":"1.0.0","tag":"v1.0","zones":[%s]}\n' "$1" > "$T/rel/release.json"
}
GOOD='{"what":"навыки","src":"skills/*","dst":"{claude}/skills/*","kind":"dir"}'
apply() { $U apply --src "$T/rel" --yes "тест" >"$T/out.txt" 2>&1; }
refused() { grep -q "отклонён" "$T/out.txt"; }

fresh; rel "$GOOD"; apply
chk "контроль: обычный релиз ставится" "[ -f $CLAUDE_CONFIG_DIR/skills/dobryj/SKILL.md ] && $U status | grep -q 1.0.0"
chk "контроль: diff обычного релиза без ошибки" "$U diff --src $T/rel >/dev/null"

fresh; rel "$GOOD,{\"what\":\"x\",\"src\":\"skills/dobryj/SKILL.md\",\"dst\":\"{home}/.bashrc\",\"kind\":\"file\"}"; apply
chk "а: dst {home}/.bashrc — отказ, файла нет" "refused && [ ! -e $HOME/.bashrc ]"
chk "е: отказ ВСЕГО манифеста — и честная зона не встала" "[ ! -e $CLAUDE_CONFIG_DIR/skills/dobryj ] && [ ! -e $CLAUDE_CONFIG_DIR/mila-update/version.json ]"
chk "е: отказ без бэкапа и без записи версии" "[ ! -d $CLAUDE_CONFIG_DIR/mila-update/backups ]"

fresh; rel '{"what":"x","src":"skills/dobryj/SKILL.md","dst":"{work}/../outside.txt","kind":"file"}'; apply
chk "в: «..» в dst — отказ, ~/outside.txt нет" "refused && [ ! -e $HOME/outside.txt ]"

fresh; rel '{"what":"x","src":"../secret.txt","dst":"{work}/stolen.txt","kind":"file"}'; apply
chk "б/в: «..» в src — отказ, чужой файл не скопирован" "refused && [ ! -e $MILA_WORK/stolen.txt ]"

fresh; ln -s "$T/secret.txt" "$T/rel/skills/dobryj/link.txt"; rel "$GOOD"; apply
chk "г: симлинк внутри навыка → на чужой файл — отказ" "refused && [ ! -e $CLAUDE_CONFIG_DIR/skills/dobryj ]"

fresh; ln "$T/secret.txt" "$T/rel/skills/dobryj/hard.txt"; rel "$GOOD"; apply
chk "г: жёсткая ссылка в релизе (st_nlink 2) — отказ" "refused && [ ! -e $CLAUDE_CONFIG_DIR/skills/dobryj ]"

fresh; ln -s "$T/secret.txt" "$T/rel/skills/f.txt"; rel '{"what":"x","src":"skills/f.txt","dst":"{work}/f.txt","kind":"file"}'; apply
chk "г: src-файл сам симлинк — отказ" "refused && [ ! -e $MILA_WORK/f.txt ]"

fresh; ln -s "$T/elsewhere" "$MILA_WORK/link"; rel '{"what":"x","src":"skills/dobryj/SKILL.md","dst":"{work}/link/f.md","kind":"file"}'; apply
chk "д: уровень пути dst — симлинк наружу — отказ, снаружи не записано" "refused && [ ! -e $T/elsewhere/f.md ]"

fresh; rel "$GOOD"; $U apply --src "$T/rel" --yes x >/dev/null 2>&1; ln -s "$T/elsewhere" "$CLAUDE_CONFIG_DIR/skills/dobryj2"
rel '{"what":"навыки","src":"skills/*","dst":"{claude}/skills/dobryj2","kind":"dir"}'; apply
chk "д: dst сам симлинк на папку наружу — отказ" "refused && [ -z \"\$(ls -A $T/elsewhere)\" ]"

fresh; rel '{"what":"x","src":"skills/dobryj/SKILL.md","dst":"{work}/NOW.md","kind":"file"}'; echo "NOW хозяина" > "$MILA_WORK/NOW.md"; apply
chk "контроль: NEVER по-прежнему тихо пропускается (NOW.md цел, не отказ)" "[ \"\$(cat $MILA_WORK/NOW.md)\" = 'NOW хозяина' ] && ! refused"

fresh; printf '{"version":"1.0.0","zones":[%s]}\n' "$GOOD" > "$T/rel/release.json"; apply
chk "tag: манифест без tag — отказ ДО бэкапа, без traceback" "grep -q 'нет tag' $T/out.txt && ! grep -q Traceback $T/out.txt && [ ! -d $CLAUDE_CONFIG_DIR/mila-update/backups ]"

fresh; rel '{"what":"x","src":"skills/dobryj/SKILL.md","dst":"{home}/.bashrc","kind":"file"}'
chk "diff плохого манифеста — отказ (код ≠ 0)" "! $U diff --src $T/rel >/dev/null 2>&1"

# --- запускатель «mila» (честный релиз кладёт его вне {claude}/{work}): ровно разрешённые пути, без ссылок
LAUNCH='{"what":"запускатель","src":"bin/mila","dst":"{home}/.local/bin/mila","kind":"file"}'
fresh; mkdir -p "$T/rel/bin"; printf '#!/bin/sh\necho mila\n' > "$T/rel/bin/mila"; rel "$GOOD,$LAUNCH"; apply
chk "запускатель: честный релиз с {home}/.local/bin/mila ставится (навык и запускатель)" "[ -f $CLAUDE_CONFIG_DIR/skills/dobryj/SKILL.md ] && [ -f $HOME/.local/bin/mila ] && grep -q 'echo mila' $HOME/.local/bin/mila && ! refused"
fresh; mkdir -p "$T/rel/bin"; echo x > "$T/rel/bin/mila"; rel '{"what":"x","src":"bin/mila","dst":"{home}/.local/bin/other","kind":"file"}'; apply
chk "запускатель: другой файл в {home}/.local/bin — по-прежнему отказ" "refused && [ ! -e $HOME/.local/bin/other ]"
fresh; mkdir -p "$T/rel/bin" "$T/elsewhere"; echo x > "$T/rel/bin/mila"; mkdir -p "$HOME/.local"; ln -s "$T/elsewhere" "$HOME/.local/bin"; rel "$LAUNCH"; apply
chk "запускатель: каталог {home}/.local/bin — ссылка наружу: отказ, снаружи не записано" "refused && [ ! -e $T/elsewhere/mila ]"
fresh; mkdir -p "$T/rel/bin" "$HOME/.local/bin"; echo x > "$T/rel/bin/mila"; echo old > "$T/secret.txt"; ln -s "$T/secret.txt" "$HOME/.local/bin/mila"; rel "$LAUNCH"; apply
chk "запускатель: сам {home}/.local/bin/mila — ссылка на чужой файл: отказ, файл цел" "refused && [ \"\$(cat $T/secret.txt)\" = old ]"
fresh; mkdir -p "$T/rel/bin"; echo x > "$T/rel/bin/mila"; rel '{"what":"x","src":"bin/mila","dst":"{home}/.local/bin/../../.bashrc","kind":"file"}'; apply
chk "запускатель: «..» в dst — отказ" "refused && [ ! -e $HOME/.bashrc ]"
fresh; mkdir -p "$T/rel/bin"; echo x > "$T/rel/bin/mila"; rel '{"what":"x","src":"bin/mila","dst":"{home}/bin/mila","kind":"file"}'; apply
chk "запускатель: прежняя догадка {home}/bin/mila (нет в release.json) — отказ" "refused && [ ! -e $HOME/bin/mila ]"
fresh; mkdir -p "$T/rel/bin" "$T/elsewhere2"; echo x > "$T/rel/bin/mila"; ln -s "$T/elsewhere2" "$HOME/.local"; rel "$LAUNCH"; apply
chk "запускатель: {home}/.local — ссылка наружу: отказ" "refused && [ ! -e $T/elsewhere2/bin/mila ]"
echo "итог $ok/$n"; [ $ok = $n ]
