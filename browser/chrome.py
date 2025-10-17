import draw_commands
import layout
import skia
from display_constants import (
    DEFAULT_FILE,
    POINTER_HOVER_TAG,
    WIDTH,
)
from event import (Focusable, Event)

BG_DEFAULT_COLOR = "white"
HOME_IMAGE = "img/home.png"
HOME_IMAGE_WIDTH = 24
HOME_IMAGE_HEIGHT = 20

def contains_point(x: int, y: int, rect: dict[str, int]):
    return x >= rect["x1"] and x < rect["x2"] and y >= rect["y1"] and y < rect["y2"]

class Chrome:
    def __init__(self, browser):
        self.browser = browser
        self.font = layout.get_font("Arial", 20, "normal", "roman")
        self.font_height = draw_commands.get_font_linespace(self.font)
        self.padding = 5
        self.tabbar_top = 0
        self.tabbar_bottom = self.font_height + 2 * self.padding
        self.urlbar_top = self.tabbar_bottom
        self.urlbar_bottom = self.urlbar_top + self.font_height + 2 * self.padding
        self.bottom = self.urlbar_bottom

        plus_width = self.font.measureText("+") + 2 * self.padding
        self.newtab_rect = {
            "x1": self.padding,
            "y1": self.padding,
            "x2": self.padding + plus_width,
            "y2": self.padding + self.font_height,
        }

        back_width = self.font.measureText("<") + 2 * self.padding
        self.back_rect = {
            "x1": self.padding,
            "y1": self.urlbar_top + self.padding,
            "x2": self.padding + back_width,
            "y2": self.urlbar_bottom - self.padding,
        }
        forward_width = self.font.measureText(">") + 2 * self.padding
        self.forward_rect = {
            "x1": self.back_rect["x2"],
            "y1": self.urlbar_top + self.padding,
            "x2": self.back_rect["x2"] + forward_width,
            "y2": self.urlbar_bottom - self.padding,
        }

        home_width = HOME_IMAGE_WIDTH + 2 * self.padding
        self.home_rect = {
            "x1": self.padding + self.forward_rect["x2"],
            "y1": self.urlbar_top + self.padding,
            "x2": self.padding + home_width + self.forward_rect["x2"],
            "y2": self.urlbar_bottom - self.padding,
        }

        self.address_rect = {
            "x1": self.padding + self.home_rect["x2"],
            "y1": self.urlbar_top + self.padding,
            "x2": WIDTH - self.padding,
            "y2": self.urlbar_bottom - self.padding,
        }
        self.focus = None
        self.address_bar_value = ""
        self.address_cursor_index = 0

    def click(self, x: int, y: int) -> bool:
        """
        Clicks on the chrome.
        """
        self.focus = None
        if contains_point(x, y, self.newtab_rect):
            # new_tab already rasters the tab
            self.browser.new_tab(DEFAULT_FILE)
        elif contains_point(x, y, self.back_rect):
            self.browser.active_tab.go_back()
        elif contains_point(x, y, self.forward_rect):
            self.browser.active_tab.go_forward()
        elif contains_point(x, y, self.home_rect):
            self.browser.active_tab.load(DEFAULT_FILE)
        elif contains_point(x, y, self.address_rect):
            self.focus = Focusable.ADDRESS_BAR
            self.address_bar_value = ""
            self.address_cursor_index = 0
        else:
            for i, tab in enumerate(self.browser.tabs):
                if contains_point(x, y, self.tab_rect(i)):
                    self.browser.active_tab = tab

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

    def enter(self) -> tuple[bool, bool]:
        """
        Presses enter on the chrome

        Returns:
            tuple[bool, bool]: [should draw chrome, should draw tab]
        """
        if self.focus == Focusable.ADDRESS_BAR:
            self.browser.active_tab.load(self.address_bar_value)
            self.focus = None
            return True, True
        return False, False

    def escape(self):
        if self.focus:
            self.focus = None
            return True
        return False

    def tab_rect(self, i):
        tabs_start = self.newtab_rect["x2"] + self.padding
        tab_width = self.font.measureText("Tab X") + 2 * self.padding
        return {
            "x1": tabs_start + tab_width * i,
            "y1": self.tabbar_top,
            "x2": tabs_start + tab_width * (i + 1),
            "y2": self.tabbar_bottom,
        }

    def paint(self):
        cmds = []
        # add background for chrome
        cmds.append(
            draw_commands.DrawRect("white", x1=0, y1=0, x2=WIDTH, y2=self.bottom)
        )
        cmds.append(
            draw_commands.DrawLine(
                "black",
                1,
                x1=0,
                y1=self.bottom,
                x2=WIDTH,
                y2=self.bottom,
            )
        )
        # add new tab button
        cmds.append(draw_commands.DrawOutline("black", 1, **self.newtab_rect))
        cmds.append(
            draw_commands.DrawText(
                "+",
                self.font,
                "black",
                x1=self.newtab_rect["x1"] + self.padding,
                y1=self.newtab_rect["y1"],
            )
        )
        # draw tabs
        for i, tab in enumerate(self.browser.tabs):
            bounds = self.tab_rect(i)
            cmds.append(
                draw_commands.DrawLine(
                    "black",
                    1,
                    **{
                        "x1": bounds["x1"],
                        "y1": 0,
                        "x2": bounds["x1"],
                        "y2": bounds["y2"],
                    },
                )
            )
            cmds.append(
                draw_commands.DrawLine(
                    "black",
                    1,
                    **{
                        "x1": bounds["x2"],
                        "y1": 0,
                        "x2": bounds["x2"],
                        "y2": bounds["y2"],
                    },
                )
            )
            cmds.append(
                draw_commands.DrawText(
                    "Tab {}".format(i),
                    self.font,
                    "black",
                    x1=bounds["x1"] + self.padding,
                    y1=bounds["y1"] + self.padding,
                )
            )
            if tab == self.browser.active_tab:
                cmds.append(
                    draw_commands.DrawLine(
                        "black",
                        1,
                        **{
                            "x1": 0,
                            "y1": bounds["y2"],
                            "x2": bounds["x1"],
                            "y2": bounds["y2"],
                        },
                    )
                )
                cmds.append(
                    draw_commands.DrawLine(
                        "black",
                        1,
                        **{
                            "x1": bounds["x2"],
                            "y1": bounds["y2"],
                            "x2": WIDTH,
                            "y2": bounds["y2"],
                        },
                    )
                )
        # draw back button
        back_tags = []
        back_color = "grey"
        if self.browser.active_tab.has_back_history():
            back_tags.append(POINTER_HOVER_TAG)
            back_color = "black"
        cmds.append(draw_commands.DrawOutline(back_color, 1, **self.back_rect))
        cmds.append(
            draw_commands.DrawText(
                "<",
                self.font,
                back_color,
                x1=self.back_rect["x1"] + self.padding,
                y1=self.back_rect["y1"],
            )
        )
        # draw forward button
        forward_tags = []
        forward_color = "grey"
        if self.browser.active_tab.has_forward_history():
            forward_tags.append(POINTER_HOVER_TAG)
            forward_color = "black"
        cmds.append(draw_commands.DrawOutline(forward_color, 1, **self.forward_rect))
        cmds.append(
            draw_commands.DrawText(
                ">",
                self.font,
                forward_color,
                x1=self.forward_rect["x1"] + self.padding,
                y1=self.forward_rect["y1"],
            )
        )
        # draw home button
        cmds.append(
            draw_commands.DrawOutline(
                "black",
                1,
                **self.home_rect,
            )
        )
        self.image = skia.Image.open(HOME_IMAGE).resize(
            HOME_IMAGE_WIDTH, HOME_IMAGE_HEIGHT
        )
        height = self.home_rect["y2"] - self.home_rect["y1"]
        extra_space = height - self.image.height()
        h_padding = round(extra_space / 2)
        cmds.append(
            draw_commands.DrawImage(
                self.image,
                x1=self.home_rect["x1"] + self.padding,
                y1=self.home_rect["y1"] + h_padding,
            )
        )
        # draw address bar
        cmds.append(draw_commands.DrawOutline("black", 1, **self.address_rect))
        has_ssl = self.browser.active_tab.has_ssl
        # TODO: change this to show lock
        if self.focus == Focusable.ADDRESS_BAR:
            cmds.append(
                draw_commands.DrawText(
                    self.address_bar_value,
                    self.font,
                    "black",
                    x1=self.address_rect["x1"] + self.padding,
                    y1=self.address_rect["y1"],
                )
            )
            w = self.font.measureText(
                self.address_bar_value[: self.address_cursor_index]
            )
            cmds.append(
                draw_commands.DrawLine(
                    "red",
                    1,
                    **{
                        "x1": self.address_rect["x1"] + self.padding + w,
                        "y1": self.address_rect["y1"],
                        "x2": self.address_rect["x1"] + self.padding + w,
                        "y2": self.address_rect["y2"],
                    },
                )
            )
        else:
            cmds.append(
                draw_commands.DrawText(
                    ("\N{lock} " if has_ssl else "\N{open lock} ") + str(self.browser.active_tab.url),
                    self.font,
                    "black",
                    x1=self.address_rect["x1"] + self.padding,
                    y1=self.address_rect["y1"],
                )
            )
        return cmds

