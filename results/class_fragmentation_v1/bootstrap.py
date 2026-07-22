"""Is the `lexical + register` coherence gain real, or corpus noise?

Paired bootstrap: resample the prompt stream with replacement, run BOTH lexical variants on the
SAME resampled stream, record the coherence difference. Lexical only -- no embedding -- so this
is cheap enough to do properly.
"""
import os, sys, tempfile, random, collections, importlib.util

os.environ['EXOCORTEX_STATE_DIR'] = tempfile.mkdtemp(prefix='boot_')
sys.path.insert(0, os.getcwd())

SP = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('vn', os.path.join(SP, 'replay.py'))
# re-use the extraction + metrics from replay.py without re-running its report
src = open(os.path.join(SP, 'replay.py'), encoding='utf-8').read()
src = src.split("print(f'{\"variant\":24s}")[0]          # stop before the report block
ns = {'__name__': 'vn'}
exec(compile(src, 'replay.py', 'exec'), ns)

items, coherence, strip_register = ns['items'], ns['coherence'], ns['strip_register']
CueClassifier = ns['CueClassifier']
texts = [it['text'] for it in items]
arts = [it['art'] for it in items]
N = len(texts)


def run(idx, prep):
    clf = CueClassifier()
    labels = []
    for i in idx:
        try:
            labels.append(clf.classify(prep(texts[i])).get('label', '?'))
        except Exception:
            labels.append('?')
    return coherence(labels, [arts[i] for i in idx])


base_plain = run(list(range(N)), lambda s: s)
base_reg = run(list(range(N)), strip_register)
print(f'observed: plain {base_plain:.4f}  register {base_reg:.4f}  '
      f'delta {base_reg - base_plain:+.4f}\n')

rnd = random.Random(20260722)
deltas = []
B = 200
for b in range(B):
    idx = [rnd.randrange(N) for _ in range(N)]
    deltas.append(run(idx, strip_register) - run(idx, lambda s: s))
    if (b + 1) % 50 == 0:
        print(f'  ...{b+1}/{B}')

deltas.sort()
lo, hi = deltas[int(.025 * B)], deltas[int(.975 * B)]
share = sum(1 for d in deltas if d > 0) / B
print(f'\nbootstrap B={B}')
print(f'  mean delta      {sum(deltas)/B:+.4f}')
print(f'  95% CI          [{lo:+.4f}, {hi:+.4f}]')
print(f'  P(delta > 0)    {share:.3f}')
print(f'  verdict: {"CI excludes 0 -> real" if lo > 0 else "CI includes 0 -> not separable from noise"}')
