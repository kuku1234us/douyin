from qt_base_app.window.base_window import BaseWindow
from douyin_app.ui.pages.dashboard_page import DashboardPage
from douyin_app.ui.pages.preferences_page import PreferencesPage
from douyin_app.ui.pages.channels_page import ChannelsPage
from douyin_app.ui.pages.video_page import VideoPage


class DouyinMainWindow(BaseWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.initialize_pages()
        self.show_page('home')
        self.sidebar.set_selected_item('home')

    def initialize_pages(self):
        self.add_page('home', DashboardPage(self))
        self.add_page('preferences', PreferencesPage(self))
        self.add_page('channels', ChannelsPage(self))
        self.add_page('video', VideoPage(self))

