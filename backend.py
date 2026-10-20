#!/usr/bin/env python3
"""Desktop mouse profiles. No raw input access, daemon, or hardware writes."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
STATE = CONFIG / 'omarchy/mouse-profiles.json'
LUA = CONFIG / 'hypr/mouse-settings.lua'
ACTIONS = {'default': None, 'back': ('ALT', 'Left'), 'forward': ('ALT', 'Right'),
           'copy': ('CTRL', 'C'), 'paste': ('CTRL', 'V'), 'undo': ('CTRL', 'Z'),
           'disabled': 'disabled'}
CODES = (272, 273, 274, 275, 276)


def run(*args):
    p = subprocess.run(args, text=True, capture_output=True, timeout=12)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout or 'Command failed')[:600])
    output = p.stdout.strip()
    if output.startswith(('Lua error', 'Error', 'error', 'failed')):
        raise RuntimeError(output[:600])
    return output


def atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load():
    if not STATE.exists():
        return {}
    data = json.loads(STATE.read_text())
    if not isinstance(data, dict) or len(data) > 100:
        raise ValueError('Invalid profiles file')
    return {name: profile for name, profile in data.items() if supported_mouse(name)}


def supported_mouse(name):
    return isinstance(name, str) and re.fullmatch(r"ergo-m575s-mouse(?:-\d+)?", name) is not None


def valid_name(name):
    return isinstance(name, str) and re.fullmatch(r'[a-z0-9_:.-]{1,160}', name)


def validate(profile):
    if not isinstance(profile, dict):
        raise ValueError('Invalid mouse profile')
    result = {}
    for key, low, high in [('sensitivity', -1, 1), ('scroll_factor', .1, 5)]:
        value = profile.get(key, 0 if key == 'sensitivity' else 1)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            raise ValueError('Invalid ' + key)
        result[key] = round(value, 2)
    for key in ('left_handed', 'natural_scroll'):
        value = profile.get(key, False)
        if not isinstance(value, bool):
            raise ValueError('Invalid ' + key)
        result[key] = value
    result['accel_profile'] = profile.get('accel_profile', 'adaptive')
    if result['accel_profile'] not in ('adaptive', 'flat'):
        raise ValueError('Invalid acceleration')
    buttons = profile.get('buttons', {})
    if not isinstance(buttons, dict) or any(k not in ('274', '275', '276') or v not in ACTIONS for k, v in buttons.items()):
        raise ValueError('Invalid button assignment')
    result['buttons'] = buttons
    return result


def discover():
    live = json.loads(run('hyprctl', 'devices', '-j'))['mice']
    # Relative pointers with a primary mouse button, on USB or Bluetooth.
    candidates = {}
    for block in Path('/proc/bus/input/devices').read_text().split('\n\n'):
        name = re.search(r'N: Name="(.*)"', block)
        bus = re.search(r'Bus=([0-9a-f]+)', block)
        key = re.search(r'B: KEY=([0-9a-f ]+)', block)
        if not (name and bus and key and 'B: REL=' in block and bus[1] in ('0003', '0005')):
            continue
        if 'keyboard' in name[1].lower():
            continue
        bitmap = sum(int(word, 16) << (64 * i) for i, word in enumerate(reversed(key[1].split())))
        if not bitmap & (1 << 272):
            continue
        normalized = re.sub(r'\s+', '-', name[1].lower())
        candidates[normalized] = (name[1][:100], [c for c in CODES if bitmap & (1 << c)])
    result = []
    for mouse in live:
        name = mouse['name']
        base = re.sub(r'-\d+$', '', name)
        match = candidates.get(name) or candidates.get(base)
        if not match or not valid_name(name) or not supported_mouse(name):
            continue
        label, buttons = match
        if name == 'ergo-m575s-mouse':
            label = 'Logitech ERGO M575S'
        result.append({'name': name, 'label': label, 'buttons': buttons,
                       'speed': max(-1, min(1, mouse.get('defaultSpeed', 0)))})
    return result[:32]


def defaults(mouse):
    def opt(key, fallback):
        data = json.loads(run('hyprctl', 'getoption', 'input:' + key, '-j'))
        value = data.get('str', data.get('bool', data.get('int', data.get('float', fallback))))
        return fallback if value in ('[[EMPTY]]', '') else value
    return validate({'sensitivity': opt('sensitivity', 0),
                     'scroll_factor': max(.1, min(5, opt('scroll_factor', 1))),
                     'left_handed': bool(opt('left_handed', 0)),
                     'natural_scroll': bool(opt('natural_scroll', 0)),
                     'accel_profile': opt('accel_profile', '') or 'adaptive'})


def lua_string(value):
    # Names and all generated strings are ASCII. JSON escaping is valid Lua here.
    return json.dumps(value, ensure_ascii=False)


def generate(profiles, mice):
    lines = ['-- Generated by diky.mouse. Edit settings in the mouse panel.',
             '-- No keybind objects retained or removed at runtime.',
             'local function add(key, callback, opts) hl.bind(key, callback, opts) end']
    names = {m['name']: m for m in mice}
    for name, raw in profiles.items():
        if not valid_name(name):
            raise ValueError('Invalid device name')
        profile = validate(raw)
        spec = ['name = ' + lua_string(name)]
        for key, val in profile.items():
            if key == 'buttons':
                continue
            spec.append(key + ' = ' + (str(val).lower() if isinstance(val, (bool, int, float)) else lua_string(val)))
        lines.append('hl.device({' + ', '.join(spec) + '})')
        names.setdefault(name, {'name': name, 'buttons': list(CODES)})
    for name, mouse in sorted(names.items()):
        profile = validate(profiles[name]) if name in profiles else {'buttons': {}}
        for code in mouse['buttons']:
            action = profile['buttons'].get(str(code), 'default')
            for release in (False, True):
                command = f'omarchy-shell -q diky.mouse buttonEvent {name} {code} ' + ('false' if release else 'true')
                callback = 'if _G.diky_mouse_watch == ' + lua_string(name) + ' then hl.exec_cmd(' + lua_string(command) + ') end; '
                if not release and isinstance(ACTIONS[action], tuple):
                    mods, key = ACTIONS[action]
                    callback += 'hl.dispatch(hl.dsp.send_shortcut({mods=' + lua_string(mods) + ', key=' + lua_string(key) + '})); '
                opts = 'device={inclusive=true,list={' + lua_string(name) + '}}, description="Mouse panel", release=' + str(release).lower()
                opts += ', non_consuming=' + str(action == 'default').lower()
                if action == 'default':
                    opts += ', transparent=true, ignore_mods=true'
                lines.append('add(' + lua_string('mouse:' + str(code)) + ', function() ' + callback + 'end, {' + opts + '})')
    return '\n'.join(lines) + '\n'


def apply(profiles, mice, persist=True):
    text = generate(profiles, mice)
    if persist:
        old = LUA.read_text() if LUA.exists() else None
        atomic(LUA, text)
        try:
            run('hyprctl', 'reload')
            errors = run('hyprctl', 'configerrors')
            if errors and errors != 'ok':
                raise RuntimeError(errors)
        except Exception:
            if old is not None:
                atomic(LUA, old)
                run('hyprctl', 'reload')
            raise
    else:
        raise ValueError('Runtime binding updates are disabled')


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'list'
    profiles = load()
    if action == 'watch':
        name = sys.argv[2]
        if name and (not valid_name(name) or not supported_mouse(name)):
            raise ValueError('Invalid device name')
        if name and ('list={' + lua_string(name) + '}') not in (LUA.read_text() if LUA.exists() else ''):
            apply(profiles, discover())
        run('hyprctl', 'eval', '_G.diky_mouse_watch = ' + lua_string(name))
        print(json.dumps({'ok': True}))
        return
    mice = discover()
    if action == 'save':
        name = sys.argv[2]
        if name not in {m['name'] for m in mice}:
            raise ValueError('Mouse disconnected; refresh the panel')
        profiles[name] = validate(json.loads(sys.argv[3]))
        apply(profiles, mice)
        atomic(STATE, json.dumps(profiles, indent=2) + '\n')
    elif action != 'list':
        raise ValueError('Unknown action')
    for mouse in mice:
        mouse['profile'] = validate(profiles[mouse['name']]) if mouse['name'] in profiles else defaults(mouse)
    print(json.dumps({'ok': True, 'mice': mice}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error)[:600]}))
        sys.exit(1)
