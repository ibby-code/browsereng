import draw_commands
import layout
import tkinter
import tkinter.font
import url
from display_constants import (
    CLEARABLE_CONTENT_TAG,
    HEIGHT,
    POINTER_HOVER_TAG,
    SCROLL_STEP,
    WIDTH,
)
from enum import Enum
from functools import partial
from PIL import ImageTk, Image
from tab import Tab

DEFAULT_BROWSER_TITLE = "CanYouBrowseIt"
BG_DEFAULT_COLOR = "white"
DEFAULT_FILE = "file://testing/test.html"
HOME_IMAGE = "img/home.png"
HOME_IMAGE_SIZE = 24


class Focusable(Enum):
    ADDRESS_BAR = "address bar"
    CONTENT = "content"


class Event(Enum):
    KEY = "<KEY>"
    ENTER = "<RETURN>"
    BACKSPACE = "backspace"
    LEFT_ARROW = "left_arrow"
    RIGHT_ARROW = "right_arrow"
    ESCAPE = "escape"


class Chrome:
    def __init__(self, browser):
        self.browser = browser
        self.font = layout.get_font("Arisl", 20, "normal", "roman")
        self.font_height = self.font.metrics("linespace")
        self.padding = 5
        self.tabbar_top = 0
        self.tabbar_bottom = self.font_height + 2 * self.padding
        self.urlbar_top = self.tabbar_bottom
        self.urlbar_bottom = self.urlbar_top + self.font_height + 2 * self.padding
        self.bottom = self.urlbar_bottom

        plus_width = self.font.measure("+") + 2 * self.padding
        self.newtab_rect = draw_commands.Rect(
            self.padding,
            self.padding,
            self.padding + plus_width,
            self.padding + self.font_height,
        )

        back_width = self.font.measure("<") + 2 * self.padding
        self.back_rect = draw_commands.Rect(
            self.padding,
            self.urlbar_top + self.padding,
            self.padding + back_width,
            self.urlbar_bottom - self.padding,
        )
        forward_width = self.font.measure(">") + 2 * self.padding
        self.forward_rect = draw_commands.Rect(
            self.back_rect.right,
            self.urlbar_top + self.padding,
            self.back_rect.right + forward_width,
            self.urlbar_bottom - self.padding,
        )

        home_width = HOME_IMAGE_SIZE + 2 * self.padding
        self.home_rect = draw_commands.Rect(
            self.padding + self.forward_rect.right,
            self.urlbar_top + self.padding,
            self.padding + home_width + self.forward_rect.right,
            self.urlbar_bottom - self.padding,
        )

        self.address_rect = draw_commands.Rect(
            self.padding + self.home_rect.right,
            self.urlbar_top + self.padding,
            WIDTH - self.padding,
            self.urlbar_bottom - self.padding,
        )
        self.focus = None
        self.address_bar_value = ""
        self.address_cursor_index = 0

    def click(self, x, y):
        self.focus = None
        if self.newtab_rect.containsPoint(x, y):
            self.browser.new_tab(DEFAULT_FILE)
        elif self.back_rect.containsPoint(x, y):
            self.browser.active_tab.go_back()
        elif self.forward_rect.containsPoint(x, y):
            self.browser.active_tab.go_forward()
        elif self.home_rect.containsPoint(x, y):
            self.browser.active_tab.load(DEFAULT_FILE)
        elif self.address_rect.containsPoint(x, y):
            self.focus = Focusable.ADDRESS_BAR
            self.address_bar_value = ""
            self.address_cursor_index = 0
        else:
            for i, tab in enumerate(self.browser.tabs):
                if self.tab_rect(i).containsPoint(x, y):
                    self.browser.active_tab = tab
                    break

    def blur(self):
        self.focus = None

    def keypress(self, char: str) -> bool:
        if self.focus == Focusable.ADDRESS_BAR:
            self.address_bar_value = (
                self.address_bar_value[: self.address_cursor_index]
                + char
                + self.address_bar_value[self.address_cursor_index :]
            )
            self.address_cursor_index = min(
                self.address_cursor_index + 1, len(self.address_bar_value)
            )
            return True
        return False

    def backspace(self) -> bool:
        if self.focus == Focusable.ADDRESS_BAR:
            self.address_bar_value = (
                self.address_bar_value[: self.address_cursor_index - 1]
                + self.address_bar_value[self.address_cursor_index :]
            )
            self.address_cursor_index = max(self.address_cursor_index - 1, 0)
            return True
        return False

    def arrow_key(self, event: Event):
        if self.focus == Focusable.ADDRESS_BAR:
            increment = 1 if event == Event.RIGHT_ARROW else -1
            new_val = self.address_cursor_index + increment
            self.address_cursor_index = min(
                max(new_val, 0), len(self.address_bar_value)
            )
            return True
        return False

    def enter(self) -> bool:
        if self.focus == Focusable.ADDRESS_BAR:
            self.browser.active_tab.load(self.address_bar_value)
            self.focus = None
            return True
        return False

    def escape(self):
        if self.focus:
            self.focus = None
            return True
        return False

    def tab_rect(self, i):
        tabs_start = self.newtab_rect.right + self.padding
        tab_width = self.font.measure("Tab X") + 2 * self.padding
        return draw_commands.Rect(
            tabs_start + tab_width * i,
            self.tabbar_top,
            tabs_start + tab_width * (i + 1),
            self.tabbar_bottom,
        )

    def paint(self):
        cmds = []
        # add background for chrome
        cmds.append(
            draw_commands.DrawRect(
                draw_commands.Rect(0, 0, WIDTH, self.bottom), "white"
            )
        )
        cmds.append(
            draw_commands.DrawLine(
                draw_commands.Rect(0, self.bottom, WIDTH, self.bottom), "black", 1
            )
        )
        # add new tab button
        cmds.append(draw_commands.DrawOutline(self.newtab_rect, "black", 1))
        cmds.append(
            draw_commands.DrawText(
                self.newtab_rect.left + self.padding,
                self.newtab_rect.top,
                "+",
                self.font,
                "black",
                tags=[POINTER_HOVER_TAG],
            )
        )
        # draw tabs
        for i, tab in enumerate(self.browser.tabs):
            bounds = self.tab_rect(i)
            cmds.append(
                draw_commands.DrawLine(
                    draw_commands.Rect(bounds.left, 0, bounds.left, bounds.bottom),
                    "black",
                    1,
                )
            )
            cmds.append(
                draw_commands.DrawLine(
                    draw_commands.Rect(bounds.right, 0, bounds.right, bounds.bottom),
                    "black",
                    1,
                )
            )
            cmds.append(
                draw_commands.DrawText(
                    bounds.left + self.padding,
                    bounds.top + self.padding,
                    "Tab {}".format(i),
                    self.font,
                    "black",
                    tags=[POINTER_HOVER_TAG],
                )
            )
            if tab == self.browser.active_tab:
                cmds.append(
                    draw_commands.DrawLine(
                        draw_commands.Rect(
                            0, bounds.bottom, bounds.left, bounds.bottom
                        ),
                        "black",
                        1,
                    )
                )
                cmds.append(
                    draw_commands.DrawLine(
                        draw_commands.Rect(
                            bounds.right, bounds.bottom, WIDTH, bounds.bottom
                        ),
                        "black",
                        1,
                    )
                )
        # draw back button
        back_tags = []
        back_color = "grey"
        if self.browser.active_tab.has_back_history():
            back_tags.append(POINTER_HOVER_TAG)
            back_color = "black"
        cmds.append(draw_commands.DrawOutline(self.back_rect, back_color, 1))
        cmds.append(
            draw_commands.DrawText(
                self.back_rect.left + self.padding,
                self.back_rect.top,
                "<",
                self.font,
                back_color,
                tags=back_tags,
            )
        )
        # draw forward button
        forward_tags = []
        forward_color = "grey"
        if self.browser.active_tab.has_forward_history():
            forward_tags.append(POINTER_HOVER_TAG)
            forward_color = "black"
        cmds.append(draw_commands.DrawOutline(self.forward_rect, forward_color, 1))
        cmds.append(
            draw_commands.DrawText(
                self.forward_rect.left + self.padding,
                self.forward_rect.top,
                ">",
                self.font,
                forward_color,
                tags=forward_tags,
            )
        )
        # draw home button
        cmds.append(draw_commands.DrawOutline(self.home_rect, "black", 1))
        self.image = load_home_image()
        height = self.home_rect.bottom - self.home_rect.top
        extra_space = height - self.image.height()
        h_padding = round(extra_space / 2)
        cmds.append(
            draw_commands.DrawImage(
                self.home_rect.left + self.padding,
                self.home_rect.top + h_padding,
                self.image,
                tags=[POINTER_HOVER_TAG],
            )
        )
        # draw address bar
        cmds.append(draw_commands.DrawOutline(self.address_rect, "black", 1))
        url = str(self.browser.active_tab.url)
        if self.focus == Focusable.ADDRESS_BAR:
            cmds.append(
                draw_commands.DrawText(
                    self.address_rect.left + self.padding,
                    self.address_rect.top,
                    self.address_bar_value,
                    self.font,
                    "black",
                )
            )
            w = self.font.measure(self.address_bar_value[: self.address_cursor_index])
            cmds.append(
                draw_commands.DrawLine(
                    draw_commands.Rect(
                        self.address_rect.left + self.padding + w,
                        self.address_rect.top,
                        self.address_rect.left + self.padding + w,
                        self.address_rect.bottom,
                    ),
                    "red",
                    1,
                )
            )
        else:
            cmds.append(
                draw_commands.DrawText(
                    self.address_rect.left + self.padding,
                    self.address_rect.top,
                    url,
                    self.font,
                    "black",
                )
            )
        return cmds


class Browser:
    def __init__(self):
        self.cookie_jar: dict[str, str] = {}
        self.url_cache: dict[url.URL, (str, int, int)] = {}
        self.tabs: list[Tab] = []
        self.active_tab: Tab | None = None
        self.window = tkinter.Tk()
        self.window.title(DEFAULT_BROWSER_TITLE)
        self.window.bind("<Key>", partial(self.handle_event, Event.KEY))
        self.window.bind("<Return>", partial(self.handle_event, Event.ENTER))
        self.window.bind("<BackSpace>", partial(self.handle_event, Event.BACKSPACE))
        self.window.bind("<Right>", partial(self.handle_event, Event.RIGHT_ARROW))
        self.window.bind("<Left>", partial(self.handle_event, Event.LEFT_ARROW))
        self.window.bind("<Escape>", partial(self.handle_event, Event.ESCAPE))
        self.window.bind("<Button-1>", self.click)
        self.window.bind("<Down>", partial(self.scroll, SCROLL_STEP))
        self.window.bind("<Up>", partial(self.scroll, -SCROLL_STEP))
        self.window.bind("<MouseWheel>", self.scroll_mouse)
        self.canvas = tkinter.Canvas(
            self.window, width=WIDTH, height=HEIGHT, bg=BG_DEFAULT_COLOR
        )
        self.canvas.tag_bind(
            POINTER_HOVER_TAG, "<Enter>", partial(self.set_cursor, "hand1")
        )
        self.canvas.tag_bind(POINTER_HOVER_TAG, "<Leave>", partial(self.set_cursor, ""))
        self.chrome = Chrome(self)
        self.canvas.pack()

    def scroll_mouse(self, e):
        delta = e.delta
        if delta % 120 == 0:
            # windows uses multiples of 120
            offset = SCROLL_STEP * (delta // 120)
        else:
            # mac uses multiples of 1
            offset = SCROLL_STEP * delta
        self.scroll(offset, e)

    def scroll(self, increment, e):
        self.active_tab.scroll(increment)
        self.draw()

    def click(self, e):
        # being called for clicks on home button / entry bar
        if e.y < self.chrome.bottom:
            self.focus = None
            self.active_tab.blur()
            self.chrome.click(e.x, e.y)
        else:
            self.focus = Focusable.CONTENT
            self.chrome.blur()
            tab_y = e.y - self.chrome.bottom
            self.active_tab.click(e.x, tab_y)
        self.draw()

    def handle_event(self, event: Event, e: tkinter.Event):
        should_draw = False
        match event:
            case Event.ENTER:
                should_draw = self.chrome.enter()
                if not should_draw and self.focus == Focusable.CONTENT:
                    should_draw = self.active_tab.enter()
            case Event.BACKSPACE:
                should_draw = self.chrome.backspace()
                if not should_draw and self.focus == Focusable.CONTENT:
                    should_draw = self.active_tab.backspace()
            case Event.LEFT_ARROW | Event.RIGHT_ARROW:
                should_draw = self.chrome.arrow_key(event)
            case Event.ESCAPE:
                should_draw = self.chrome.escape()
            case Event.KEY:
                if len(e.char) == 0:
                    return
                if not (0x20 <= ord(e.char) < 0x7F):
                    return
                should_draw = self.chrome.keypress(e.char)
                if not should_draw and self.focus == Focusable.CONTENT:
                    should_draw = self.active_tab.keypress(e.char)
        if should_draw:
            self.draw()

    def set_cursor(self, cursor, e):
        # print("set cursor", cursor)
        self.canvas.config(cursor=cursor)

    def load_url(self, e=None):
        url_value = self.url_value.get()
        print(url_value)
        if url_value:
            self.active_tab.load(url_value)
            self.draw()

    def new_tab(self, url):
        new_tab = Tab(self.cookie_jar, self.url_cache, HEIGHT - self.chrome.bottom)
        new_tab.load(url)
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        self.draw()

    def draw(self):
        self.canvas.delete(CLEARABLE_CONTENT_TAG)
        title = (
            self.active_tab.title if self.active_tab.title else DEFAULT_BROWSER_TITLE
        )
        self.window.title(title)
        self.active_tab.draw(self.canvas, self.chrome.bottom)
        # TODO: add tabs to clearable content
        for cmd in self.chrome.paint():
            cmd.execute(0, self.canvas)


def load_home_image():
    im = Image.open(HOME_IMAGE)
    im.thumbnail((HOME_IMAGE_SIZE, HOME_IMAGE_SIZE), Image.Resampling.LANCZOS)
    home_img = ImageTk.PhotoImage(im)
    return home_img


if __name__ == "__main__":
    import sys

    if not len(sys.argv) > 1:
        arg = DEFAULT_FILE
    else:
        arg = sys.argv[1]
    b = Browser()
    b.new_tab(arg)
    tkinter.mainloop()
