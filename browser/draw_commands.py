import skia
from dataclasses import dataclass, field

NAMED_COLORS = {
    "black": "#000000",
    "silver": "#c0c0c0",
    "gray": "#808080",
    "grey": "#808080",
    "white": "#ffffff",
    "maroon": "#800000",
    "red": "#ff0000",
    "purple": "#800080",
    "fuchsia": "#ff00ff",
    "green": "#008000",
    "lime": "#00ff00",
    "olive": "#808000",
    "yellow": "#ffff00",
    "navy": "#000080",
    "blue": "#0000ff",
    "teal": "#008080",
    "aqua": "#00ffff",
    "lightblue": "#add8e6",
    "orange": "#ffa500",
}


def parse_color(color: str) -> skia.Color:
    if color.startswith("#"):
        if len(color) == 7:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            return skia.Color(r, g, b)
        elif len(color) == 4:
            r = int(color[1] * 2, 16)
            g = int(color[2] * 2, 16)
            b = int(color[3] * 2, 16)
            return skia.Color(r, g, b)
        else:
            print("could not parse color", color)
            return skia.ColorBLACK
    elif color in NAMED_COLORS:
        return parse_color(NAMED_COLORS[color])
    else:
        print("missing color", color)
        return skia.ColorBLACK


def get_font_linespace(font: skia.Font) -> int:
    metrics = font.getMetrics()
    return metrics.fDescent - metrics.fAscent


@dataclass
class DrawObject:
    x1: int = field(kw_only=True, default=None)
    x2: int = field(kw_only=True, default=None)
    y1: int = field(kw_only=True, default=None)
    y2: int = field(kw_only=True, default=None)
    tags: list[str] = field(kw_only=True, default_factory=list)
    rect: skia.Rect = field(init=False)

    def __post_init__(self):
        self.rect = skia.Rect.MakeLTRB(self.x1, self.y1, self.x2, self.y2)


@dataclass
class DrawOutline(DrawObject):
    color: str
    thickness: int

    def execute(self, scroll, canvas, tags=[]):
        tags.extend(self.tags)
        paint = skia.Paint(
            Color=parse_color(self.color),
            StrokeWidth=self.thickness,
            Style=skia.Paint.kStroke_Style,
        )
        canvas.drawRect(self.rect.makeOffset(0, -scroll), paint)


@dataclass
class DrawLine(DrawObject):
    color: str
    thickness: int

    def execute(self, scroll, canvas, tags=[]):
        tags.extend(self.tags)
        # this doesn't look right from the book, shouldn't scroll adjust y?
        path = (
            skia.Path()
            .moveTo(self.x1, self.y1 - scroll)
            .lineTo(self.x2, self.y2 - scroll)
        )
        paint = skia.Paint(
            Color=parse_color(self.color),
            StrokeWidth=self.thickness,
            Style=skia.Paint.kStroke_Style,
        )
        canvas.drawPath(path, paint)


@dataclass
class DrawImage(DrawObject):
    image: skia.Image

    def __post_init__(self):
        pass

    def execute(self, scroll, canvas, tags=[]):
        tags.extend(self.tags)
        canvas.drawImage(self.image, self.x1, self.y1 - scroll)


@dataclass()
class DrawText(DrawObject):
    text: str
    font: skia.Font
    color: str
    bottom: int = field(init=False)

    def __post_init__(self):
        self.bottom = self.y1 + get_font_linespace(self.font)
        self.rect = skia.Rect.MakeLTRB(
            self.x1, self.y1, self.x1 + self.font.measureText(self.text), self.bottom
        )

    def execute(self, scroll, canvas, tags=[]):
        tags.extend(self.tags)
        paint = skia.Paint(
            AntiAlias=True,
            Color=parse_color(self.color),
        )
        baseline = self.y1 - scroll - self.font.getMetrics().fAscent
        canvas.drawString(self.text, float(self.x1), baseline, self.font, paint)


@dataclass()
class DrawRect(DrawObject):
    color: str

    def execute(self, scroll, canvas, tags=[]):
        tags.extend(self.tags)
        paint = skia.Paint(Color=parse_color(self.color))
        canvas.drawRect(self.rect.makeOffset(0, -scroll), paint)


@dataclass()
class DrawRRect(DrawObject):
    color: str
    radius: int
    rrect: skia.RRect = field(init=False)

    def __post_init__(self):
        super().__post_init__()
        self.rrect = skia.RRect.MakeRectXY(self.rect, self.radius, self.radius)

    def execute(self, scroll, canvas, tags=[]):
        tags.extend(self.tags)
        paint = skia.Paint(Color=parse_color(self.color))
        canvas.drawRRect(self.rrect.makeOffset(0, -scroll), paint)
