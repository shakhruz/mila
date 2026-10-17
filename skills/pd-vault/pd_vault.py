#!/usr/bin/env python3
"""pd_vault.py — personal data vault of a Mila (layer 2a of the core, on by default; owner 17.10.2026).
Personal data in what Mila STORES and PASSES ON (memory, cards, journals, reports, notes to other Milas, exports) is replaced by a short
label like ⟦тел·1⟧; the value goes to an encrypted vault in the Mila's home. Same value → same label. Reveal — only for the owner, in his DM.
Honest limit: the model sees an incoming message whole (otherwise Mila can't answer). The vault protects what is kept and forwarded.
Detects: phone numbers, e-mails, bank card numbers (Luhn), Uzbek passport (AA1234567), PINFL (14 digits). Addresses, health — by the skill's rules.
  pd_vault.py mask  < text            → text with labels (values stored)
  pd_vault.py mask-file FILE…         → same, in place (only if something changed); prints labels added
  pd_vault.py scan FILE…              → what kind of data is where (no values) — exit 1 if found
  pd_vault.py reveal LABEL            → the value (owner only — the skill decides)
  pd_vault.py init                    → create the key (600) if missing
Key: $PD_KEY (default ~/.config/mila/pd.key, 32 random bytes hex). Vault: $PD_VAULT (default ~/work/state/pd/vault.enc).
Encryption: openssl AES-256-CBC (PBKDF2 from the key) + HMAC-SHA256 over the ciphertext (tamper → refuse). Stdlib + openssl only."""
import hashlib, hmac, json, os, re, secrets, subprocess, sys

KEYF = os.path.expanduser(os.environ.get("PD_KEY", "~/.config/mila/pd.key"))
VAULT = os.path.expanduser(os.environ.get("PD_VAULT", "~/work/state/pd/vault.enc"))
KINDS = {"phone": "тел", "email": "почта", "card": "карта", "passport": "паспорт", "pinfl": "ПИНФЛ"}
LABEL_RE = re.compile(r"⟦(тел|почта|карта|паспорт|ПИНФЛ)·\d+⟧")

PAT = [
    ("email", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("card", re.compile(r"(?<!\d)(?:\d{4}[ -]?){3}\d{4}(?!\d)")),
    ("pinfl", re.compile(r"(?<!\d)[3-6]\d{13}(?!\d)")),
    ("phone", re.compile(r"(?<![\w+])(?:\+?998[ -]?\(?\d{2}\)?|\+\d{1,3}[ -]?\(?\d{2,4}\)?|\b8[ -]?\(?\d{3}\)?)[ -]?\d{2,3}[ -]?\d{2}[ -]?\d{2,3}(?!\d)")),
    ("passport", re.compile(r"(?<![A-Za-z])[A-Z]{2} ?\d{7}(?!\d)")),
]


def _luhn(d):
    s, alt = 0, False
    for ch in reversed(d):
        n = int(ch)
        if alt:
            n *= 2
            if n > 9: n -= 9
        s += n; alt = not alt
    return s % 10 == 0


def find(text):
    """[(start, end, kind, value)] без пересечений, слева направо; карта — только по Луну."""
    hits, taken = [], []
    for kind, rx in PAT:
        for m in rx.finditer(text):
            v = m.group(0)
            if kind == "card" and not _luhn(re.sub(r"\D", "", v)): continue
            if any(m.start() < e and s < m.end() for s, e in taken): continue
            if LABEL_RE.search(text[max(0, m.start() - 2):m.end() + 2]): continue
            hits.append((m.start(), m.end(), kind, v)); taken.append((m.start(), m.end()))
    return sorted(hits)


def _key():
    try: k = open(KEYF).read().strip()
    except OSError: sys.exit("pd_vault: no key " + KEYF + " — run: pd_vault.py init")
    if not re.fullmatch(r"[0-9a-f]{64}", k): sys.exit("pd_vault: bad key")
    return k


def init():
    if os.path.exists(KEYF): return False
    os.makedirs(os.path.dirname(KEYF), mode=0o700, exist_ok=True)
    fd = os.open(KEYF, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, (secrets.token_hex(32) + "\n").encode()); os.close(fd)
    return True


def _crypt(data, k, dec=False):
    args = ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "100000", "-salt", "-pass", "env:PDK"] + (["-d"] if dec else [])
    r = subprocess.run(args, input=data, capture_output=True, env={"PDK": k, "PATH": os.environ.get("PATH", "/usr/bin:/bin")})
    if r.returncode: raise RuntimeError("openssl: " + r.stderr.decode(errors="replace")[:200])
    return r.stdout


def load():
    if not os.path.exists(VAULT): return {"next": {}, "by_value": {}, "by_label": {}}
    k = _key(); blob = open(VAULT, "rb").read()
    tag, ct = blob[:32], blob[32:]
    if not hmac.compare_digest(tag, hmac.new(bytes.fromhex(k), ct, hashlib.sha256).digest()): sys.exit("pd_vault: vault tampered or wrong key — refused")
    return json.loads(_crypt(ct, k, dec=True))


def save(v):
    k = _key(); os.makedirs(os.path.dirname(VAULT), mode=0o700, exist_ok=True)
    ct = _crypt(json.dumps(v, ensure_ascii=False).encode(), k)
    tmp = VAULT + ".tmp"
    with open(tmp, "wb") as f: f.write(hmac.new(bytes.fromhex(k), ct, hashlib.sha256).digest() + ct)
    os.chmod(tmp, 0o600); os.replace(tmp, VAULT)


def _norm(kind, v):
    return v.lower() if kind == "email" else re.sub(r"[^\dA-Z+]", "", v.upper())


def mask(text, v=None):
    """→ (masked, added_labels). v — открытое хранилище (для пакетной правки), иначе load/save здесь."""
    own = v is None
    hits = find(text)
    if not hits: return text, []
    v = v or load(); added = []
    out, pos = [], 0
    for s, e, kind, val in hits:
        key = kind + ":" + _norm(kind, val)
        lab = v["by_value"].get(key)
        if not lab:
            n = v["next"].get(kind, 0) + 1; v["next"][kind] = n
            lab = "⟦%s·%d⟧" % (KINDS[kind], n); v["by_value"][key] = lab; v["by_label"][lab] = val; added.append(lab)
        out.append(text[pos:s]); out.append(lab); pos = e
    out.append(text[pos:])
    if own and added: save(v)
    return "".join(out), added


def main(a):
    if not a: sys.exit(__doc__)
    c = a[0]
    if c == "init": print("created" if init() else "exists"); return 0
    if c == "mask":
        t, _ = mask(sys.stdin.read()); sys.stdout.write(t); return 0
    if c == "mask-file":
        v = load(); total = []
        for f in a[1:]:
            try: t = open(f, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError): continue
            m, added = mask(t, v)
            if m != t:
                tmp = f + ".pdtmp"; open(tmp, "w", encoding="utf-8").write(m); os.replace(tmp, f); total += added
        if total: save(v)
        print(json.dumps({"masked_new": total}, ensure_ascii=False)); return 0
    if c == "scan":
        found = 0
        for f in a[1:]:
            try: t = open(f, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError): continue
            kinds = sorted({k for _, _, k, _ in find(t)})
            if kinds: found += 1; print(f + ": " + ", ".join(KINDS[k] for k in kinds))
        return 1 if found else 0
    if c == "reveal":
        val = load()["by_label"].get(a[1]) if len(a) > 1 else None
        if not val: print("no such label", file=sys.stderr); return 2
        print(val); return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
