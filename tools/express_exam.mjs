// ЭКСПРЕСС-ЭКЗАМЕН ядра (skills/exam; владелец MILAGPT 17.10): те же сценарии, что гоняет юзербот, — внутри, через подписку Claude (Haiku), без Telegram.
// Гость = claude -p с промптом гостя ровно как в бою (--prompt + --extra разметка моста), свежая сессия на сценарий,
// ходы — --resume, шапка гостя как у моста. Оценка — отдельный ход Haiku по «ждём / провал» экзамена → pass/fail + цитата.
// bun express_exam.mjs --yaml scenarii.yaml --prompt GUEST-PROMPT-v2.md [--par 5] [--only 1,4] [--out runs/]
import { spawn } from 'child_process'
import { createHash } from 'crypto'
import { randomUUID } from 'crypto'
import * as fs from 'fs'; import os from 'os'; import { join, dirname, resolve } from 'path'

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d }
const YAML = arg('yaml', ''), PROMPT = resolve(arg('prompt', ''))
if (import.meta.main && (!YAML || !arg('prompt', ''))) { console.error('usage: bun tools/express_exam.mjs --yaml exam.yaml --prompt GUEST-PROMPT.md [--extra markup.md] [--repeat 3] [--par 5] [--out runs/]'); process.exit(2) }
const REP = +arg('repeat', 1), PAR = +arg('par', 5), ONLY = arg('only', ''), OUT = arg('out', 'runs'), MODEL = arg('model', 'haiku'), JUDGE = arg('judge', 'haiku')
const BIN = process.env.CLAUDE_BIN || 'claude'

// переходник: свой формат {scenarios:[{id,turns,expect,fail,must,lang}]} или yaml стенда (steps/messages/say → turns, criteria/pass → expect)
export function scenariosOf(doc) {
  const list = Array.isArray(doc) ? doc : doc.scenarios || doc.cases || doc.tests || []
  const txt = (v) => Array.isArray(v) ? v.map(x => '· ' + x).join(' ') : String(v || '')
  return list.filter(s => !s.skip && !s.nosell).map((s, i) => ({   // nosell (№9) решает мост, не CC — покрыт тестом моста
    id: String(s.id ?? s.n ?? i + 1).replace(/^s0?/, ''), name: s.name || s.title || '', lang: s.lang || 'ru', must: !!(s.required || s.mandatory || s.must === true),
    turns: (s.turns || s.steps || s.messages || s.say || []).map(t => typeof t === 'string' ? t : t.text || t.say || (t.button ? '[кнопка] ' + t.button : '')).filter(Boolean),
    expect: txt(s.expect || s.must || s.criteria || s.pass || s.ждём), fail: txt(s.fail || s.must_not || s.провал),
  }))
}

function run(args, cwd, ms = 120000) {
  return new Promise((res) => {
    let out = '', done = false
    const p = spawn(BIN, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, ANTHROPIC_BASE_URL: '', ANTHROPIC_AUTH_TOKEN: '' } })
    const t = setTimeout(() => { if (!done) { done = true; p.kill('SIGKILL'); res({ err: 'timeout' }) } }, ms)
    p.stdout.on('data', b => out += b); p.stderr.on('data', () => {})
    p.on('close', () => { if (done) return; done = true; clearTimeout(t); try { res({ j: JSON.parse(out.slice(out.indexOf('{'))) }) } catch { res({ err: 'no json: ' + out.slice(0, 200) }) } })
  })
}
// что видит гость: метки моста вырезаны, кнопки — словами
export const seen = (t) => String(t || '').replace(/\[\[(card|gap|paid):[^\]]*\]\]/g, '').replace(/\[\[schet:(\w+)\]\]/g, '[счёт $1: карточка + 4 кнопки]')
  .replace(/\[\[btn:([^\]]+)\]\]/g, '[кнопка «$1»]').replace(/\[\[url:([^\]|]+)\|[^\]]+\]\]/g, '[кнопка-ссылка «$1»]').trim()

async function judgeRaw(s, dir) {
  const log = s.log
  const tr = log.map(x => `Гость: ${x.g}\nМила: ${seen(x.m)}`).join('\n\n')
  const q = `Ты экзаменатор «Пути гостя» бота Милы. Сценарий №${s.id} «${s.name}».\nЖдём: ${s.expect}\nПровал: ${s.fail}\n\nРазговор (как видит гость):\n${tr}\n\n` +
    `Оцени строго по «ждём/провал». Ответь ТОЛЬКО JSON: {"pass": true|false, "why": "одна фраза", "quote": "дословная цитата из ответа Милы, на которой решение"}`
  const j = await run(['-p', q, '--model', JUDGE, '--output-format', 'json', '--setting-sources', '', '--tools', '', '--strict-mcp-config'], dir, 90000)
  let v = { pass: false, why: 'оценка не вышла: ' + (j.err || ''), quote: '' }
  if (j.j) { try { v = JSON.parse(String(j.j.result).slice(String(j.j.result).indexOf('{'), String(j.j.result).lastIndexOf('}') + 1)) } catch { v.why = 'оценка не JSON' } }
  return { v, c: j.j?.total_cost_usd || 0 }
}
async function judge(s, work) { return (await judgeRaw(s, fs.mkdtempSync(join(work, 'p' + s.id + '-')))).v }

// язык реплики — как у моста: кириллица → ru; узбекская латиница (oʻ, gʻ, sh/ch, kerak, men, siz) → uz; прочая латиница → en; служебное (/start, кнопка) — прежний
function langGuess(t) {
  const u = String(t || '').replace(/^\[кнопка\][^]*$/, '').replace(/^\/\w+/, '').trim(); if (!u) return null
  if (/[а-яё]/i.test(u)) return 'ru'
  if (/[oOgG][ʻ'`’]|\b(kerak|men|siz|qanday|salom|rahmat|ko'r|bilan|uchun)\b/i.test(u)) return 'uz'
  return /[a-z]/i.test(u) ? 'en' : null
}
async function scenario(s, pf, work) {
  const sid = randomUUID(), dir = fs.mkdtempSync(join(work, 's' + s.id + '-')), log = []
  let cost = 0, t0 = Date.now(), lastLang = 'ru'
  for (let i = 0; i < s.turns.length; i++) {
    const lg = s.lang !== 'ru' ? s.lang : langGuess(s.turns[i]) || (i ? lastLang : 'ru'); lastLang = lg
    const head = `[гость tg 9000${s.id} · Тест Экзамен · язык ${lg} (отвечай на нём)${i ? ' · приветствие уже было — не здоровайся заново' : ''}${i === 2 && !log.some(x => /\[\[btn:Да, сч/.test(x.m)) ? ' · это твой 3-й ответ: строка пользы под его дело + тест-драйв кнопкой [[btn:Да, счёт]]' : ''}]`
    const r = await run(['-p', head + ' ' + s.turns[i], '--model', MODEL, '--output-format', 'json', '--setting-sources', '', '--disable-slash-commands',
      '--tools', 'Read', '--allowedTools', 'Read', '--strict-mcp-config', '--system-prompt-file', pf, ...(i ? ['--resume', sid] : ['--session-id', sid])], dir)
    if (r.err) { log.push({ g: s.turns[i], m: '⛔ ' + r.err }); break }
    cost += r.j.total_cost_usd || 0
    log.push({ g: s.turns[i], m: String(r.j.result || '') })
  }
  const { v, c } = await judgeRaw({ ...s, log }, dir); cost += c
  return { ...s, log, verdict: v, sec: Math.round((Date.now() - t0) / 1000), cost }
}

if (import.meta.main) {
  const t0 = Date.now()
  let sc = scenariosOf(Bun.YAML.parse(fs.readFileSync(YAML, 'utf8')))
  if (ONLY) sc = sc.filter(s => ONLY.split(',').includes(s.id))
  const work = fs.mkdtempSync(join(os.tmpdir(), 'express-'))
  const pf = join(work, 'prompt.txt')
  // промпт ровно как в бою: файл промпта + (необязательно) разметка моста/кнопок, которую ваш мост добавляет к промпту
  fs.writeFileSync(pf, fs.readFileSync(PROMPT, 'utf8') + (arg('extra', '') ? '\n' + fs.readFileSync(arg('extra', ''), 'utf8') : ''))
  // --repeat N: каждый сценарий N раз — итог «k/N», сценарий сдан при большинстве (разброс Haiku виден, а не прячется)
  const jobs = sc.flatMap(s => Array.from({ length: REP }, () => s)), runs = []; let k = 0
  await Promise.all(Array.from({ length: PAR }, async () => { while (k < jobs.length) { const s = jobs[k++]; runs.push(await scenario(s, pf, work)) } }))
  const res = sc.map(s => { const rs = runs.filter(r => r.id === s.id), n = rs.filter(r => r.verdict.pass).length
    const pick = rs.find(r => r.verdict.pass === (n * 2 > rs.length)) || rs[0]
    return { ...pick, k: n, of: rs.length, verdict: { ...pick.verdict, pass: n * 2 > rs.length }, cost: rs.reduce((a, r) => a + r.cost, 0) } })
  // подложенные провалы: последний ответ Милы подменён заведомо плохим — оценка обязана сказать ❌
  const doc = Bun.YAML.parse(fs.readFileSync(YAML, 'utf8')), plants = (doc.plants || []).filter(p => res.find(r => r.id === String(p.id)))
  const caught = await Promise.all(plants.map(async (p) => {
    const r = res.find(x => x.id === String(p.id)), fake = { ...r, log: [...r.log.slice(0, -1), { ...r.log.at(-1), m: p.answer }] }
    const v = await judge(fake, work); return { id: String(p.id), caught: v.pass === false, why: v.why }
  }))
  const ok = res.filter(r => r.verdict.pass).length, mustBad = res.filter(r => r.must && !r.verdict.pass).map(r => r.id)
  const stamp = new Date(Date.now() + 5 * 3600e3).toISOString().slice(0, 16).replace('T', ' ')
  const sha = createHash('sha256').update(fs.readFileSync(PROMPT)).digest('hex').slice(0, 16), shaFull = createHash('sha256').update(fs.readFileSync(pf)).digest('hex').slice(0, 16)
  const md = [`# Экспресс «${YAML.split('/').pop()}» · ${stamp} (UTC+5) · ${MODEL}, подписка${REP > 1 ? ` · каждый сценарий ×${REP}` : ''}`, `Промпт: ${PROMPT} · sha256 ${sha} (с разметкой моста ${shaFull}) — сверять с промптом в бою`,
    `Не покрыто экспрессом (Качество 17.10): навыки дома Милы (--setting-sources '' — они не грузятся), мост (кнопки, счёт, «не продавать») — это тесты моста и живой прогон.`,
    `**Итог: ${ok}/${res.length}**${mustBad.length ? ` · обязательные не сданы: ${mustBad.join(', ')}` : ' · обязательные сданы'}${caught.length ? ` · подложенные провалы пойманы: ${caught.filter(c => c.caught).length}/${caught.length}` : ''} · ${Math.round((Date.now() - t0) / 1000)} с · $${res.reduce((a, r) => a + r.cost, 0).toFixed(3)} (по счётчику, подписка)`, '',
    '| # | сценарий | итог | почему | цитата |', '|---|---|---|---|---|',
    ...res.map(r => `| ${r.id}${r.must ? '*' : ''} | ${r.name} | ${r.verdict.pass ? '✅' : '❌'}${r.of > 1 ? ` ${r.k}/${r.of}` : ''} | ${String(r.verdict.why || '').replace(/\|/g, '/')} | ${String(r.verdict.quote || '').replace(/\|/g, '/').replace(/\n/g, ' ').slice(0, 160)} |`), '',
    ...(caught.some(c => !c.caught) ? ['**Оценка пропустила подложенный провал:** ' + caught.filter(c => !c.caught).map(c => c.id + ' (' + c.why + ')').join('; '), ''] : []),
    ...res.map(r => `## ${r.id}. ${r.name}\n` + r.log.map(x => `> ${x.g}\n\n${seen(x.m)}`).join('\n\n'))].join('\n')
  fs.mkdirSync(OUT, { recursive: true })
  const f = join(OUT, `express-${stamp.replace(/[ :]/g, '')}.md`); fs.writeFileSync(f, md)
  fs.writeFileSync(f.replace(/\.md$/, '.json'), JSON.stringify(res, null, 1))
  console.log(md.split('\n').slice(0, res.length + 7).join('\n')); console.log('\n→ ' + f)
}
