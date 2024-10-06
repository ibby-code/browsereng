import ctypes
import draw_commands
import math
import layout
import sdl2
import skia
import url
from display_constants import (
    HEIGHT,
    POINTER_HOVER_TAG,
    SCROLL_STEP,
    WIDTH,
    VSTEP,
)
from enum import Enum
from PIL import ImageTk, Image
from tab import Tab

DEFAULT_BROWSER_TITLE = "CanYouBrowseIt"
BG_DEFAULT_COLOR = "white"
DEFAULT_FILE = "file://testing/test.html"
HOME_IMAGE = "img/home.png"
HOME_IMAGE_WIDTH = 24
HOME_IMAGE_HEIGHT = 20


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
        
        Returns:
            bool: True to raster the tab (only chrome is raster'd by default)
        """
        self.focus = None
        if contains_point(x, y, self.newtab_rect):
            # new_tab already rasters the tab
            self.browser.new_tab(DEFAULT_FILE)
        elif contains_point(x, y, self.back_rect):
            self.browser.active_tab.go_back()
            return True
        elif contains_point(x, y, self.forward_rect):
            self.browser.active_tab.go_forward()
            return True
        elif contains_point(x, y, self.home_rect):
            self.browser.active_tab.load(DEFAULT_FILE)
            return True
        elif contains_point(x, y, self.address_rect):
            self.focus = Focusable.ADDRESS_BAR
            self.address_bar_value = ""
            self.address_cursor_index = 0
        else:
            for i, tab in enumerate(self.browser.tabs):
                if contains_point(x, y, self.tab_rect(i)):
                    self.browser.active_tab = tab
                    return True

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
        url = str(self.browser.active_tab.url)
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
                    url,
                    self.font,
                    "black",
                    x1=self.address_rect["x1"] + self.padding,
                    y1=self.address_rect["y1"],
                )
            )
        return cmds


class Browser:
    def __init__(self):
        self.cookie_jar: dict[str, str] = {}
        self.url_cache: dict[url.URL, (str, int, int)] = {}
        self.tabs: list[Tab] = []
        self.active_tab: Tab | None = None
        if sdl2.SDL_BYTEORDER == sdl2.SDL_BIG_ENDIAN:
            self.color_masks = {
                "RED_MASK": 0xFF000000,
                "GREEN_MASK": 0x00FF0000,
                "BLUE_MASK": 0x0000FF00,
                "ALPHA_MASK": 0x000000FF,
            }
        else:
            self.color_masks = {
                "RED_MASK": 0x000000FF,
                "GREEN_MASK": 0x0000FF00,
                "BLUE_MASK": 0x00FF0000,
                "ALPHA_MASK": 0xFF000000,
            }
        self.root_surface = skia.Surface.MakeRaster(
            skia.ImageInfo.Make(
                WIDTH, HEIGHT, ct=skia.kRGBA_8888_ColorType, at=skia.kUnpremul_AlphaType
            )
        )
        self.sdl_window = sdl2.SDL_CreateWindow(
            DEFAULT_BROWSER_TITLE.encode(),
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            WIDTH,
            HEIGHT,
            sdl2.SDL_WINDOW_SHOWN,
        )
        # TODO: Get cursor changing on hover for sdl:SDL_SetCursor()
        self.chrome = Chrome(self)
        self.chrome_surface = skia.Surface(WIDTH, math.ceil(self.chrome.bottom))
        self.tab_surface = None

    def scroll_mouse(self, e: sdl2.SDL_MouseWheelEvent):
        delta = e.y
        if delta:
            self.scroll(delta * SCROLL_STEP, e)

    def scroll(self, increment: int, e: sdl2.SDL_Event):
        self.active_tab.scroll(increment)
        self.raster_tab()
        self.draw()

    def click(self, e: sdl2.SDL_MouseButtonEvent):
        # being called for clicks on home button / entry bar
        if e.y < self.chrome.bottom:
            self.focus = None
            self.active_tab.blur()
            should_raster_tab = self.chrome.click(e.x, e.y)
            self.raster_chrome()
            if should_raster_tab:
                self.raster_tab()
        else:
            self.focus = Focusable.CONTENT
            self.chrome.blur()
            tab_y = e.y - self.chrome.bottom
            self.active_tab.click(e.x, tab_y)
            self.raster_tab()
        self.draw()

    def handle_event(self, event: Event, e: sdl2.SDL_Event):
        should_draw_chrome = False
        should_draw_tab = False
        match event:
            case Event.ENTER:
                (should_draw_chrome, should_draw_tab) = self.chrome.enter()
                if not should_draw_chrome and self.focus == Focusable.CONTENT:
                    should_draw_tab = self.active_tab.enter()
            case Event.BACKSPACE:
                should_draw_chrome = self.chrome.backspace()
                if not should_draw_chrome and self.focus == Focusable.CONTENT:
                    should_draw_tab = self.active_tab.backspace()
            case Event.LEFT_ARROW | Event.RIGHT_ARROW:
                should_draw_chrome = self.chrome.arrow_key(event)
            case Event.ESCAPE:
                should_draw_chrome = self.chrome.escape()
            case Event.KEY:
                char = e.text.text.decode("utf8")
                if len(char) == 0:
                    return
                if not (0x20 <= ord(char) < 0x7F):
                    return
                should_draw_chrome = self.chrome.keypress(char)
                if not should_draw_chrome and self.focus == Focusable.CONTENT:
                    should_draw_tab = self.active_tab.keypress(char)
        if should_draw_chrome or should_draw_tab:
            if should_draw_chrome:
                self.raster_chrome()
            if should_draw_tab:
                self.raster_tab()
            self.draw()

    def set_cursor(self, cursor, e):
        # print("set cursor", cursor)
        pass
        # self.canvas.config(cursor=cursor)

    def new_tab(self, url):
        new_tab = Tab(self.cookie_jar, self.url_cache, HEIGHT - self.chrome.bottom)
        new_tab.load(url)
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        self.raster_chrome()
        self.raster_tab()
        self.draw()
    
    def raster_tab(self):
        tab_height = math.ceil(self.active_tab.document.height + 2 * VSTEP)
        if not self.tab_surface or tab_height != self.tab_surface.height():
            self.tab_surface = skia.Surface(WIDTH, tab_height)
        canvas = self.tab_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)
        self.active_tab.raster(canvas)
    
    def raster_chrome(self):
        canvas = self.chrome_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)
        for cmd in self.chrome.paint():
            cmd.execute(canvas)

    def draw(self):
        title = (
            self.active_tab.title if self.active_tab.title else DEFAULT_BROWSER_TITLE
        )
        canvas = self.root_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)

        tab_rect = skia.Rect.MakeLTRB(
            0, self.chrome.bottom, WIDTH, HEIGHT)
        tab_offset = self.chrome.bottom - self.active_tab.scroll_offset
        canvas.save()
        canvas.clipRect(tab_rect)
        canvas.translate(0, tab_offset)
        self.tab_surface.draw(canvas, 0, 0)
        canvas.restore()

        chrome_rect = skia.Rect.MakeLTRB(
            0, 0, WIDTH, self.chrome.bottom)
        canvas.save()
        canvas.clipRect(chrome_rect)
        self.chrome_surface.draw(canvas, 0, 0)
        canvas.restore()
        # take a snapshot of skia and pass it to sdl
        depth = 32  # Bits per pixel
        pitch = 4 * WIDTH  # Bytes per row
        skia_image = self.root_surface.makeImageSnapshot()
        skia_bytes = skia_image.tobytes()
        sdl_surface = sdl2.SDL_CreateRGBSurfaceFrom(
            skia_bytes,
            WIDTH,
            HEIGHT,
            depth,
            pitch,
            self.color_masks["RED_MASK"],
            self.color_masks["GREEN_MASK"],
            self.color_masks["BLUE_MASK"],
            self.color_masks["ALPHA_MASK"],
        )
        rect = sdl2.SDL_Rect(0, 0, WIDTH, HEIGHT)
        window_surface = sdl2.SDL_GetWindowSurface(self.sdl_window)
        sdl2.SDL_SetWindowTitle(self.sdl_window, title.encode())
        # SDL_BlitSurface is copying the values
        sdl2.SDL_BlitSurface(sdl_surface, rect, window_surface, rect)
        sdl2.SDL_UpdateWindowSurface(self.sdl_window)

    def handle_quit(self):
        sdl2.SDL_DestroyWindow(self.sdl_window)


def contains_point(x: int, y: int, rect: dict[str, int]):
    return x >= rect["x1"] and x < rect["x2"] and y >= rect["y1"] and y < rect["y2"]


def mainloop(browser: Browser):
    event = sdl2.SDL_Event()
    while True:
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            match event.type:
                case sdl2.SDL_QUIT:
                    browser.handle_quit()
                    sdl2.SDL_Quit()
                    sys.exit()
                case sdl2.SDL_MOUSEBUTTONUP:
                    browser.click(event.button)
                case sdl2.SDL_KEYDOWN:
                    match event.key.keysym.sym:
                        case sdl2.SDLK_RETURN:
                            browser.handle_event(Event.ENTER, event)
                        case sdl2.SDLK_DOWN:
                            browser.scroll(SCROLL_STEP, event)
                        case sdl2.SDLK_UP:
                            browser.scroll(-SCROLL_STEP, event)
                        case sdl2.SDLK_BACKSPACE:
                            browser.handle_event(Event.BACKSPACE, event)
                        case sdl2.SDLK_LEFT:
                            browser.handle_event(Event.LEFT_ARROW, event)
                        case sdl2.SDLK_RIGHT:
                            browser.handle_event(Event.RIGHT_ARROW, event)
                        case sdl2.SDLK_ESCAPE:
                            browser.handle_event(Event.ESCAPE, event)
                case sdl2.SDL_TEXTINPUT:
                    browser.handle_event(Event.KEY, event)
                case sdl2.SDL_MOUSEWHEEL:
                    browser.scroll_mouse(event.wheel)


if __name__ == "__main__":
    import sys

    sdl2.SDL_Init(sdl2.SDL_INIT_EVENTS)

    if not len(sys.argv) > 1:
        arg = DEFAULT_FILE
    else:
        arg = sys.argv[1]
    b = Browser()
    b.new_tab(arg)
    mainloop(b)
