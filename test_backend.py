import unittest
from unittest.mock import patch
import backend


class MouseProfiles(unittest.TestCase):
    def test_reject_command_and_lua_injection(self):
        for name in ['mouse;touch /tmp/test', 'mouse\"})', 'mouse\n', '../mouse']:
            self.assertFalse(backend.valid_name(name))
            with self.assertRaises(ValueError):
                backend.generate({name: {}}, [])

    def test_invalid_profiles_do_not_reach_compositor(self):
        for profile in [{'sensitivity': float('nan')}, {'sensitivity': 2},
                        {'left_handed': 'false'}, {'buttons': {'272': 'disabled'}},
                        {'buttons': {'274': 'exec rm'}}, {'scroll_factor': 0}]:
            with self.assertRaises(ValueError):
                backend.validate(profile)

    def test_default_clicks_pass_through_and_observation_is_gated(self):
        lua = backend.generate({}, [{'name':'test-mouse','buttons':[272,274]}])
        self.assertIn('non_consuming=true', lua)
        self.assertIn('if _G.diky_mouse_watch == "test-mouse" then', lua)
        self.assertIn('device={inclusive=true,list={"test-mouse"}}', lua)
        self.assertNotIn('send_shortcut', lua)

    def test_shortcut_only_for_assigned_device_and_on_press(self):
        lua = backend.generate({'mouse-one': {'buttons': {'275': 'copy'}}},
                               [{'name':'mouse-one','buttons':[275]}, {'name':'mouse-two','buttons':[275]}])
        self.assertEqual(lua.count('send_shortcut'), 1)
        self.assertIn('mods="CTRL", key="C"', lua)
        self.assertIn('non_consuming=false', lua)

    def test_failed_reload_restores_previous_config(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            lua = Path(folder)/'test.lua'
            lua.write_text('-- original\n')
            with patch.object(backend, 'LUA', lua), patch.object(backend, 'run', side_effect=['ok', 'bad config', 'ok']):
                with self.assertRaises(RuntimeError):
                    backend.apply({}, [])
            self.assertEqual(lua.read_text(), '-- original\n')

    def test_no_runtime_binding_objects(self):
        lua=backend.generate({}, [{'name':'test-mouse','buttons':[272]}])
        self.assertNotIn(':remove()', lua)
        self.assertNotIn('table.insert', lua)
        with self.assertRaises(ValueError):
            backend.apply({}, [], persist=False)

    def test_discovery_handles_zero_words_in_kernel_bitmap(self):
        from pathlib import Path
        fixture='I: Bus=0005 Vendor=046d Product=b041 Version=0009\nN: Name="ERGO M575S Mouse"\nB: KEY=ffff0000 0 0 0 0\nB: REL=1943\n'
        with patch.object(Path,'read_text',return_value=fixture), patch.object(backend,'run',return_value='{"mice":[{"name":"ergo-m575s-mouse","defaultSpeed":0}]}'):
            mice=backend.discover()
        self.assertEqual(mice[0]['buttons'],[272,273,274,275,276])

    def test_only_logitech_ergo_is_discovered(self):
        from pathlib import Path
        import json
        fixture=''
        for vendor, name in [('046d','ERGO M575S Mouse'),('32c2','Nulea M514 Mouse'),('3938','BT mouse')]:
            fixture += f'I: Bus=0005 Vendor={vendor} Product=0001 Version=0001\nN: Name="{name}"\nB: KEY=ffff0000 0 0 0 0\nB: REL=1943\n\n'
        live={'mice':[{'name':name,'defaultSpeed':0} for name in ['ergo-m575s-mouse','nulea-m514-mouse','bt-mouse']]}
        with patch.object(Path,'read_text',return_value=fixture), patch.object(backend,'run',return_value=json.dumps(live)):
            mice=backend.discover()
        self.assertEqual([m['name'] for m in mice],['ergo-m575s-mouse'])

    def test_setup_works_inside_plugin_directory_and_is_idempotent(self):
        import os, runpy, shutil, subprocess, tempfile
        from pathlib import Path
        from contextlib import redirect_stdout
        from io import StringIO
        source=Path(__file__).parent
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)
            target=config/'omarchy/plugins/diky.mouse'
            target.mkdir(parents=True)
            for file in ['install.py','backend.py','Panel.qml','MousePicture.qml','manifest.json']:
                shutil.copy2(source/file,target/file)
            shutil.copytree(source/'i18n',target/'i18n')
            main=config/'hypr/hyprland.lua'
            main.parent.mkdir()
            main.write_text('-- existing user configuration\n')
            result=subprocess.CompletedProcess([],0,'Enabled diky.mouse','')
            with patch.dict(os.environ,{'XDG_CONFIG_HOME':temp}), patch.object(backend,'load',return_value={}), patch.object(backend,'discover',return_value=[]), patch('subprocess.run',return_value=result), patch('subprocess.check_output',return_value=''), redirect_stdout(StringIO()):
                runpy.run_path(str(target/'install.py'))
                runpy.run_path(str(target/'install.py'))
            self.assertEqual(main.read_text().count('-- Mouse panel desktop profiles'),1)
            self.assertTrue(main.read_text().startswith('-- existing user configuration'))
            self.assertEqual(len(list((config/'omarchy/backups').iterdir())),2)

    def test_markup_device_label_stays_data(self):
        # All UI text, including device names and backend errors, uses PlainText.
        from pathlib import Path
        source=(Path(__file__).parent/'Panel.qml').read_text()
        self.assertIn('textFormat: Text.PlainText',source)
        self.assertIn('root.mouse.label',source)  # Ui.Button also uses PlainText.
        self.assertNotIn('tooltipText: modelData.label',source)

if __name__ == '__main__':
    unittest.main()
