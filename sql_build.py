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
    msg_view = None
    msg_view_lock = threading.Lock()
    scheme_pattern = re.compile(rb'^\s*--\s*uri\s*=\s*(?P<uri>.*://[^\s]+)$')
    encoding = 'utf8'

    def is_enable(self, kill=False):
        if kill:
            return self.proc is not None and self.proc.poll() is None
        return True

    def run(self, kill=False, new_tab=False):
        if kill:
            if self.proc:
                self.killed = True
                self.proc.terminate()
            return

        vars = self.window.extract_variables()
        working_dir = vars['file_path']
        source_file = vars['file']

        with self.msg_view_lock:
            if new_tab:
                self.msg_view = self.window.new_file(
                    flags=sublime.NewFileFlags.NONE,
                    syntax='Packages/JSON/JSON.sublime-syntax',
                )
            else:
                self.msg_view = self.window.create_output_panel('exec')
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

                    for pipe in (self.proc.stdout, self.proc.stderr):
                        if not pipe:
                            continue
                        threading.Thread(target=self._read_pipe, args=(pipe,)).start()
                    break
            else:
                self._queue_write(
                    '\ndatabase file not found, add it with "uri={SCHEME}" comment'
                )

    def _read_pipe(self, pipe: IO[bytes]):
        try:
            for line in iter(pipe.readline, b''):
                self._queue_write(line.decode(self.encoding).strip())
        except UnicodeDecodeError as e:
            self._queue_write(f'\nError decoding output using {self.encoding} - {e}')
        except IOError:
            if self.killed:
                msg = 'Cancelled'
            else:
                msg = 'Finished'
            self._queue_write(f'\n{msg}')
        except Exception as e:
            self._queue_write(f'\nError occured: {e}')

    def _queue_write(self, text):
        sublime.set_timeout(lambda: self._do_write(text), 1)

    def _do_write(self, text):
        with self.msg_view_lock:
            self.msg_view.run_command('append', {'characters': text})
