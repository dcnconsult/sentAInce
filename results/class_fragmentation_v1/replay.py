"""Verb/noun classification variants, judged by CONSEQUENCE rather than by eye.

The semantic replay failed on precision: MiniLM captured the PI's conversational register
("lets look at our X and determine Y") rather than task identity, fusing 24 unrelated lexical
classes into one. The lexical classifier's stoplist is deliberately verb-preserving -- task
verbs ("run", "test", "add") ARE intent -- but it cannot tell a task verb from a DISCOURSE verb
("lets", "look", "think", "keep", "going"), so the register survives into the cue either way.

Hypothesis: strip discourse scaffolding, keep task verbs + content nouns, and BOTH the singleton
rate and the merge precision improve.

GROUND TRUTH IS INDEPENDENT OF WORDING. For each prompt we collect what the session actually DID
next -- tool names and file basenames from the following assistant turns. Two prompts are "the
same task" to the degree their downstream artifact sets overlap (Jaccard). A classifier is
precise if the prompts it groups actually led to the same work. That is this project's own
epistemology (consequence, not appearance) turned on its own classifier.

Calibrated against a NULL: the same class-size distribution assigned at random. A classifier
only earns credit for coherence ABOVE what its class sizes alone would produce.
"""
import json, glob, os, sys, re, tempfile, random, collections, statistics

SCRATCH = tempfile.mkdtemp(prefix='verbnoun_')
os.environ['EXOCORTEX_STATE_DIR'] = SCRATCH
sys.path.insert(0, os.getcwd())

# Claude Code stores a repo's session transcripts under ~/.claude/projects/<slug>, where the slug
# is the repo's absolute path with every separator (and the drive colon) replaced by '-'. Derive it
# from the repo you are standing in so this replays on ANY corpus, not just the one it was written
# against; EXOCORTEX_TRANSCRIPT_DIR overrides for a corpus stored elsewhere.
PROJ = os.environ.get('EXOCORTEX_TRANSCRIPT_DIR') or os.path.join(
    os.path.expanduser('~/.claude/projects'),
    re.sub(r'[:\\/]', '-', os.path.abspath(os.environ.get('EXOCORTEX_REPLAY_ROOT') or os.getcwd())))
SKIP = ('<local-command-caveat>', '<command-name>', '<command-message>', '<command-args>',
        '<system-reminder>', '<persisted-output>', '<task-notification>')


def text_of(msg):
    c = msg.get('content')
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return '\n'.join(b.get('text', '') for b in c
                         if isinstance(b, dict) and b.get('type') == 'text')
    return ''


def artifacts_of(msg):
    """Tool calls in one assistant message -> {tool, tool:basename, bash:verb}."""
    out = set()
    c = msg.get('content')
    if not isinstance(c, list):
        return out
    for b in c:
        if not (isinstance(b, dict) and b.get('type') == 'tool_use'):
            continue
        name = str(b.get('name') or '')
        out.add(f'tool:{name}')
        inp = b.get('input') or {}
        if isinstance(inp, dict):
            p = inp.get('file_path') or inp.get('path') or inp.get('notebook_path')
            if p:
                out.add('file:' + os.path.basename(str(p)).lower())
            cmd = inp.get('command')
            if cmd and name in ('Bash', 'PowerShell'):
                m = re.search(r'[a-zA-Z_][\w.-]*', str(cmd))
                if m:
                    out.add('cmd:' + m.group(0).lower())
    return out


# ---- build (prompt, downstream artifacts) pairs, chronologically ----
items, seen = [], set()
for f in sorted(glob.glob(os.path.join(PROJ, '*.jsonl'))):
    entries = []
    for line in open(f, encoding='utf-8-sig'):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    cur = None
    for r in entries:
        msg = r.get('message') or {}
        c = msg.get('content')
        # CRITICAL: in Claude Code transcripts tool RESULTS arrive as type="user" entries
        # (6,074 of 6,584 here). Treating them as prompt boundaries severs attribution at the
        # first tool result and discards the rest of the turn -- measured 5.7% capture vs 82%.
        if isinstance(c, list) and any(isinstance(b, dict) and b.get('type') == 'tool_result'
                                       for b in c):
            continue
        if r.get('type') == 'user' and not r.get('isMeta') and not r.get('isSidechain'):
            t = text_of(msg).strip()
            if t and not any(m in t[:400] for m in SKIP) and len(t) >= 8 and t not in seen:
                seen.add(t)
                cur = {'ts': r.get('timestamp') or '', 'text': t, 'art': set()}
                items.append(cur)
            else:
                cur = None
        elif r.get('type') == 'assistant' and cur is not None:
            cur['art'] |= artifacts_of(msg)

items.sort(key=lambda x: x['ts'])
items = [it for it in items if it['art']]          # need consequence to judge against
print(f'prompts with downstream consequence: {len(items)}')
print(f'median artifacts/prompt: {statistics.median(len(i["art"]) for i in items):.0f}\n')

# ---- the register stoplist: discourse scaffolding, NOT task verbs ----
DISCOURSE = set("""
lets let go going goes went get gets got getting look looking looks see seeing think thinks
thinking feel feels feeling want wants need needs needed keep keeping keeps take takes taking
now next then also just well ok okay yes no yeah sure maybe please thanks thank thing things
way ways time times good great nice lot lots bit little much many more most some any able
really actually basically probably maybe perhaps something anything everything nothing
consider considering determine determining start starting begin lets us our we you i my your
before after while during today tomorrow yesterday session sessions work working works
""".split())

# task verbs we explicitly PROTECT even if they look generic -- these are intent
TASK_VERBS = set("""
build run test commit push publish release deploy gauge measure fix add remove refactor
document scope wire merge revert install analyze verify audit prove ship park retire
""".split())

_TOK = re.compile(r"[a-zA-Z0-9_]+")


def strip_register(text: str) -> str:
    toks = [t.lower() for t in _TOK.findall(text)]
    keep = [t for t in toks if t in TASK_VERBS or (t not in DISCOURSE and len(t) > 2)]
    return ' '.join(keep) or text


def content_only(text: str) -> str:
    """Aggressive: task verbs + long content tokens only (proxy for verb+noun)."""
    toks = [t.lower() for t in _TOK.findall(text)]
    keep = [t for t in toks if t in TASK_VERBS or (t not in DISCOURSE and len(t) >= 5)]
    return ' '.join(keep) or strip_register(text)


from exocortex.cue_classifier import CueClassifier                 # noqa: E402
from exocortex.embed_classifier import EmbeddingCueClassifier      # noqa: E402

VARIANTS = [
    ('lexical (ships)',      CueClassifier,           lambda s: s),
    ('semantic',             EmbeddingCueClassifier,  lambda s: s),
    ('lexical + register',   CueClassifier,           strip_register),
    ('semantic + register',  EmbeddingCueClassifier,  strip_register),
    ('lexical content-only', CueClassifier,           content_only),
    ('semantic content-only', EmbeddingCueClassifier, content_only),
]


def jac(a, b):
    u = len(a | b)
    return len(a & b) / u if u else 0.0


def coherence(labels, arts):
    """Mean pairwise downstream-Jaccard WITHIN class, over multi-member classes."""
    g = collections.defaultdict(list)
    for i, lb in enumerate(labels):
        g[lb].append(i)
    sims, weights = [], 0
    for idx in g.values():
        if len(idx) < 2:
            continue
        ps = [jac(arts[i], arts[j])
              for a, i in enumerate(idx) for j in idx[a + 1:]]
        sims.append(sum(ps) / len(ps) * len(ps))
        weights += len(ps)
    return (sum(sims) / weights) if weights else 0.0


def null_coherence(labels, arts, trials=20, seed=20260722):
    rnd = random.Random(seed)
    sizes = collections.Counter(labels)
    pool = list(range(len(labels)))
    out = []
    for _ in range(trials):
        rnd.shuffle(pool)
        fake, k = [None] * len(labels), 0
        for lb, n in sizes.items():
            for _i in range(n):
                fake[pool[k]] = lb
                k += 1
        out.append(coherence(fake, arts))
    return sum(out) / len(out)


arts = [it['art'] for it in items]
texts = [it['text'] for it in items]

print(f'{"variant":24s} {"cls":>5s} {"singl":>6s} {"rate":>7s} {"top":>4s} '
      f'{"coher":>7s} {"null":>7s} {"lift":>7s}')
print('-' * 74)
for name, ctor, prep in VARIANTS:
    clf = ctor()
    labels = []
    for t in texts:
        try:
            labels.append(clf.classify(prep(t)).get('label', '?'))
        except Exception:
            labels.append('?')
    c = collections.Counter(labels)
    single = sum(1 for v in c.values() if v == 1)
    coh = coherence(labels, arts)
    nul = null_coherence(labels, arts)
    lift = (coh / nul) if nul else 0.0
    print(f'{name:24s} {len(c):5d} {single:6d} {single/len(c)*100:6.1f}% {max(c.values()):4d} '
          f'{coh:7.4f} {nul:7.4f} {lift:6.2f}x')
