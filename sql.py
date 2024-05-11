# coding: utf-8

import os
import re
import subprocess
from sys import stderr, stdout
import threading
from pathlib import Path
from typing import IO

import sublime
import sublime_plugin


class SqlRunCommand(sublime_plugin.WindowCommand):
    proc = None
    killed = False
    panel = None
    panel_lock = threading.Lock()
    path_pattern = re.compile(r'\s*--\s*([^\s]+)')
    encoding = 'utf8'

    def is_enable(self, kill=False):
        if kill:
            return self.proc is not None and self.proc.poll() is None
        return True

    def run(self, kill=False):
        if kill:
            if self.proc:
                self.killed = True
                self.proc.terminate()
            return

        vars = self.window.extract_variables()
        working_dir = vars['file_path']
        source_file = vars['file']

        with self.panel_lock:
            self.panel = self.window.create_output_panel('exec')

            settings = self.panel.settings()
            settings.set(
                'result_file_regex',
                r'^File "([^"]+)" line (\d+) col (\d+)',
            )
            settings.set(
                'result_line_regex',
                r'^\s+line (\d+) col (\d+)',
            )
            settings.set('result_base_dir', working_dir)

            self.window.run_command('show_panel', {'panel': 'output.exec'})

        if self.proc is not None:
            self.proc.terminate()
            self.proc = None

        with Path(source_file).open(mode='r', encoding=self.encoding) as fp:
            for line in iter(fp.readline, ''):
                if m := self.path_pattern.match(line):
                    db_filepath = Path(m.group(1)).expanduser()
                    if not db_filepath.exists():
                        continue
                    self.proc = subprocess.Popen(
                        [
                            'usql',
                            '-f',
                            source_file,
                            '-J',
                            '-q',
                            f'file:///{db_filepath}',
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=working_dir,
                        shell=True,
                    )
                    self.killed = False

                    threading.Thread(
                        target=self.read_handle,
                        args=(self.proc.stdout, self.proc.stderr),
                    ).start()
                    break
            else:
                self.queue_write('db file not found, add it with comment')

    def read_handle(self, std_out: IO[bytes], std_err: IO[bytes]):
        try:
            for pipe in (std_err, std_out):
                for line in iter(pipe.readline, b''):
                    self.queue_write(line.decode(self.encoding, "ignore").strip())
        except UnicodeDecodeError as e:
            self.queue_write(f'Error decoding output using {self.encoding} - {e}')
        except IOError:
            if self.killed:
                msg = 'Cancelled'
            else:
                msg = 'Finished'

            self.queue_write(f'\n{msg}')

    def queue_write(self, text):
        sublime.set_timeout(lambda: self.do_write(text), 1)

    def do_write(self, text):
        with self.panel_lock:
            self.panel.run_command('append', {'characters': text})
