import ctypes
import math
import sdl2
import skia
import url
from chrome import Chrome
from display_constants import (
    DEFAULT_FILE,
    HEIGHT,
    SCROLL_STEP,
    WIDTH,
    VSTEP,
)
from event import (Focusable, Event)
from tab import Tab

DEFAULT_BROWSER_TITLE = "CanYouBrowseIt"

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
            url = self.active_tab.url
            self.active_tab.click(e.x, tab_y)
            if self.active_tab.url != url:
                self.raster_chrome()
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
        self.chrome.address_bar_value = str(new_tab.url) 
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
        browser.active_tab.task_runner.run()


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
