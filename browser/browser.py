import ctypes
import math
import sdl2
import skia
import threading
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
from measure_time import MeasureTime
from tab import Tab
from tab_commit_data import CommitData
from task import Task

DEFAULT_BROWSER_TITLE = "CanYouBrowseIt"
REFRESH_RATE_SEC = 0.033

class Browser:
    def __init__(self):
        self.cookie_jar: dict[str, str] = {}
        self.url_cache: dict[url.URL, (str, int, int)] = {}
        self.tabs: list[Tab] = []
        self.active_tab: Tab | None = None
        self.animation_timer = None
        self.needs_raster_and_draw = False
        self.needs_animation_frame = True 
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
        self.measure = MeasureTime()
        # TODO: Get cursor changing on hover for sdl:SDL_SetCursor()
        self.chrome = Chrome(self)
        self.chrome_surface = skia.Surface(WIDTH, math.ceil(self.chrome.bottom))
        self.tab_surface = None
        self.lock = threading.Lock()
        threading.current_thread().name = "Browser thread"

        self.active_tab_data: CommitData = CommitData(
            "", 0, 0, [], False, False, False, 0
        )

    def set_needs_raster_and_draw(self):
        self.lock.acquire(blocking=True)
        self.needs_raster_and_draw = True
        self.lock.release()

    def set_needs_animation_frame(self, tab):
        self.lock.acquire(blocking=True)
        if tab == self.active_tab:
            self.needs_animation_frame = True 
        self.lock.release()
        
    def commit(self, tab: Tab, data: CommitData):
        self.lock.acquire(blocking=True)
        if tab == self.active_tab:
            self.active_tab_data = data
            self.animation_timer = None
            self.lock.release()
            self.set_needs_raster_and_draw()
        else:
            self.lock.release()

    def scroll_mouse(self, e: sdl2.SDL_MouseWheelEvent):
        delta = e.y
        if delta:
            self.scroll(delta * SCROLL_STEP, e)

    def scroll(self, increment: int, e: sdl2.SDL_Event):
        self.lock.acquire(blocking=True)
        task = Task(self.active_tab.scroll, increment)
        self.active_tab.task_runner.schedule_task(task)
        self.raster_tab()
        self.draw()
        self.lock.release()

    def click(self, e: sdl2.SDL_MouseButtonEvent):
        # being called for clicks on home button / entry bar
        self.lock.acquire(blocking=True)
        needs_animation_frame = False
        if e.y < self.chrome.bottom:
            self.focus = None
            task = Task(self.active_tab.blur)
            self.active_tab.task_runner.schedule_task(task)
            needs_animation_frame= self.chrome.click(e.x, e.y)
        else:
            self.focus = Focusable.CONTENT
            self.chrome.blur()
            tab_y = e.y - self.chrome.bottom
            task = Task(self.active_tab.click, e.x, tab_y)
            self.active_tab.task_runner.schedule_task(task)
        self.lock.release()
        if needs_animation_frame:
            self.set_needs_animation_frame(self.active_tab)
        else:
            self.set_needs_raster_and_draw()

    def handle_event(self, event: Event, e: sdl2.SDL_Event):
        should_draw_chrome = False
        #should_draw_tab = False
        self.lock.acquire(blocking=True)
        match event:
            case Event.ENTER:
                should_draw_chrome = self.chrome.enter()
                if not should_draw_chrome and self.focus == Focusable.CONTENT:
                    task = Task(self.active_tab.enter)
                    self.active_tab.task_runner.schedule_task(task)
            case Event.BACKSPACE:
                should_draw_chrome = self.chrome.backspace()
                if not should_draw_chrome and self.focus == Focusable.CONTENT:
                    task = Task(self.active_tab.backspace)
                    self.active_tab.task_runner.schedule_task(task)
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
                    task = Task(self.active_tab.keypress, char)
                    self.active_tab.task_runner.schedule_task(task)
        self.lock.release()
        if should_draw_chrome:
            self.set_needs_raster_and_draw()

    def set_cursor(self, cursor, e):
        # print("set cursor", cursor)
        pass
        # self.canvas.config(cursor=cursor)
    
    def schedule_animation_frame(self):
        def callback():
            self.lock.acquire(blocking=True)
            active_tab = self.active_tab
            task = Task(active_tab.run_animation_frame)
            active_tab.task_runner.schedule_task(task)
            self.animation_timer = None
            self.lock.release()
        self.lock.acquire(blocking=True)
        if self.needs_animation_frame and not self.animation_timer:
            self.needs_animation_frame = False
            self.animation_timer = threading.Timer(REFRESH_RATE_SEC, callback)
            self.animation_timer.start()
        self.lock.release()

    def schedule_load(self, url, body=None):
        self.active_tab.task_runner.clear_pending_tasks()
        task = Task(self.active_tab.load, url, body)
        self.active_tab.task_runner.schedule_task(task)

    def new_tab(self, url):
        self.lock.acquire(blocking=True)
        self.new_tab_internal(url)
        self.lock.release()
    
    def new_tab_internal(self, url):
        new_tab = Tab(self, self.cookie_jar, self.url_cache, HEIGHT - self.chrome.bottom)
        new_tab.task_runner.start_thread()
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        self.chrome.address_bar_value = str(new_tab.url) 
        self.schedule_load(url)
    
    def raster_and_draw(self):
        self.lock.acquire(blocking=True)
        if not self.needs_raster_and_draw:
            self.lock.release()
            return
        self.measure.time('raster_and_draw')
        self.raster_chrome()
        self.raster_tab()
        self.draw()
        self.needs_raster_and_draw = False
        self.measure.stop('raster_and_draw')
        self.lock.release()

    def raster_tab(self):
        tab_height = math.ceil(self.active_tab_data.document_height + 2 * VSTEP)
        if not self.tab_surface or tab_height != self.tab_surface.height():
            self.tab_surface = skia.Surface(WIDTH, tab_height)
        canvas = self.tab_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)

        for cmd in self.active_tab_data.display_list:
            cmd.execute(canvas)
    
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
        for tab in self.tabs:
            tab.task_runner.set_needs_quit()
        sdl2.SDL_DestroyWindow(self.sdl_window)
        self.measure.finish()


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
        browser.raster_and_draw()
        browser.schedule_animation_frame()


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
