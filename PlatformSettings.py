import sublime
import sublime_plugin


class PlatformSettingsEventListener(sublime_plugin.EventListener):
    _PLATFORM_SETTINGS = '__platform_settings'
    _PLATFORM_SETTING_VALID = '__platform_setting_valid'

    def _update_settings(self, view, is_first=False):
        platform = sublime.platform()
        settings = view.settings()

        if not is_first:
            is_first = not settings.get(self._PLATFORM_SETTING_VALID, False)
        if not is_first:
            settings.clear_on_change(self._PLATFORM_SETTINGS)

        platform_settings = settings.get(platform, None)
        if platform_settings:
            for k, v in platform_settings.items():
                curr = settings.get(k, None)
                if curr != v:
                    settings.set(k, v)

        def on_change():
            self._update_settings(view)

        settings.set(self._PLATFORM_SETTING_VALID, True)
        settings.add_on_change(self._PLATFORM_SETTINGS, lambda: sublime.set_timeout(on_change, 0))

    def on_activate(self, view):
        self._update_settings(view)
        pass

    def on_new(self, view):
        self._update_settings(view, True)
        pass

    def on_load(self, view):
        self._update_settings(view, True)
        pass
