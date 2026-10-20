"""Verify a live scroll setting, profile persistence and isolation; restore in finally."""
import json
import subprocess
import time
import backend

mice=backend.discover()
mouse=next(m for m in mice if m['name']=='ergo-m575s-mouse')
profiles=backend.load()
original=profiles.get(mouse['name'],backend.defaults(mouse))
def live():
    return {m['name']:m['scrollFactor'] for m in json.loads(backend.run('hyprctl','devices','-j'))['mice']}
before=live()
trial=dict(original,sensitivity=.1 if original['sensitivity']!=.1 else .15,scroll_factor=1.2 if original['scroll_factor']!=1.2 else 1.3)
helper=str(backend.Path(__file__).parent/'backend.py')
try:
    result=json.loads(backend.run('python3',helper,'save',mouse['name'],json.dumps(trial)))
    assert result['ok'],result
    for attempt in range(30):
        after=live()
        if abs(after[mouse['name']]-trial['scroll_factor'])<.001:
            break
        time.sleep(.1)
    assert abs(after[mouse['name']]-trial['scroll_factor'])<.001,after
    for name,value in before.items():
        if name!=mouse['name']:
            assert after[name]==value,(name,before,after)
    saved=backend.load()
    assert saved[mouse['name']]['sensitivity']==trial['sensitivity']
    print('PASS: selected mouse scroll setting applied; other mice unchanged; speed profile persisted.')
finally:
    backend.run('python3',helper,'save',mouse['name'],json.dumps(original))
    for attempt in range(30):
        restored=live()
        if restored==before:
            break
        time.sleep(.1)
    assert restored==before,(before,restored)
    print('PASS: original mouse settings restored; compositor config is clean.')
