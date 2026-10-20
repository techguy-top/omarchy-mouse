#!/usr/bin/env python3
import datetime
import backend
import os
from pathlib import Path
import shutil
import subprocess
import time

source = Path(__file__).resolve().parent
config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))
target = config/'omarchy/plugins/diky.mouse'
backup = config/'omarchy/backups'/('mouse-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
backup.mkdir(parents=True)
for path in [config/'omarchy/shell.json', config/'hypr/hyprland.lua', config/'hypr/mouse-settings.lua', config/'omarchy/mouse-profiles.json']:
    if path.exists():
        shutil.copy2(path, backup/path.name)
if target.exists():
    shutil.copytree(target, backup/'diky.mouse', ignore=shutil.ignore_patterns('.git', '__pycache__'))
target.mkdir(parents=True, exist_ok=True)
for filename in ['manifest.json', 'Panel.qml', 'MousePicture.qml', 'backend.py']:
    if (source/filename).resolve() != (target/filename).resolve():
        shutil.copy2(source/filename, target/filename)
if (source/'i18n').resolve() != (target/'i18n').resolve():
    shutil.copytree(source/'i18n', target/'i18n', dirs_exist_ok=True)
lua = config/'hypr/mouse-settings.lua'
lua.write_text(backend.generate(backend.load(), backend.discover()))
main = config/'hypr/hyprland.lua'
marker = '-- Mouse panel desktop profiles (diky.mouse)'
if marker not in main.read_text():
    with main.open('a') as stream:
        stream.write('\n' + marker + '\ndofile((os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/hypr/mouse-settings.lua")\n')
subprocess.run(['omarchy','plugin','validate',str(target)], check=True)
subprocess.run(['hyprctl','reload'],check=True)
errors=subprocess.check_output(['hyprctl','configerrors'],text=True).strip()
if errors and errors != 'ok':
    shutil.copy2(backup/'hyprland.lua',main)
    subprocess.run(['hyprctl','reload'],check=True)
    raise RuntimeError(errors)
subprocess.run(['omarchy-shell','shell','rescanPlugins'],check=True)
for attempt in range(15):
    result = subprocess.run(['omarchy','plugin','enable','diky.mouse','--section','right','--before','omarchy.monitor'],capture_output=True,text=True)
    if result.returncode == 0:
        print(result.stdout.strip())
        break
    time.sleep(.2)
else:
    raise RuntimeError(result.stderr)
print('Backup:', backup)
