# coding: utf-8

import re
import subprocess
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
    scheme_pattern = re.compile(rb'^\s*--\s*uri\s*=\s*(?P<uri>.*://[^\s]+)$')
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
            self.window.run_command('show_panel', {'panel': 'output.exec'})

        if self.proc is not None:
            self.proc.terminate()
            self.proc = None

        with Path(source_file).open(mode='rb') as fp:
            for line in iter(fp.readline, b''):
                if m := self.scheme_pattern.match(line):
                    uri = m.group('uri').decode(encoding=self.encoding)
                    self.proc = subprocess.Popen(
                        ['usql', '-J', '-f', source_file, '-q', uri],
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
                self.queue_write('db file not found, add it with "uri={SCHEME}"')

    def read_handle(self, std_out: IO[bytes], std_err: IO[bytes]):
        try:
            for pipe in (std_out, std_err):
                for line in iter(pipe.readline, b''):
                    self.queue_write(line.decode(self.encoding, "ignore").strip())
        except UnicodeDecodeError as e:
            self.queue_write(f'\nError decoding output using {self.encoding} - {e}')
        except IOError:
            if self.killed:
                msg = 'Cancelled'
            else:
                msg = 'Finished'

            self.queue_write(f'\n{msg}')
        except Exception as e:
            self.queue_write(f'error occur: {e}')

    def queue_write(self, text):
        sublime.set_timeout(lambda: self.do_write(text), 1)

    def do_write(self, text):
        with self.panel_lock:
            self.panel.run_command('append', {'characters': text})
