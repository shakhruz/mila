# Express exam — example

Check a sales Mila in under a minute after every prompt change (see [skills/exam](../../skills/exam/SKILL.md)).

```sh
bun tools/express_exam.mjs --yaml docs/exam-example/exam.example.yaml --prompt docs/exam-example/guest-prompt.example.md --repeat 3
```

Needs [Bun](https://bun.sh) and Claude Code logged in with your Claude subscription. Each scenario runs in a fresh session; a separate judge turn checks `must` / `must_not` and quotes the reply.
The header of the report has the prompt's sha256 — compare it with the prompt your bot really uses. `plants` are deliberately bad replies: the judge must fail them.
Replace the example prompt with your own guest prompt and add your bridge markup with `--extra`.

**RU:** пример экспресс-экзамена: замените промпт своим, гоняйте после каждой правки; живой прогон ботом — раз в сутки по тому же yaml.
