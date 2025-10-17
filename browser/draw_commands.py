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


def parse_color(color: str, default: skia.Color = skia.ColorBLACK) -> skia.Color:
    if color.startswith("#"):
        if len(color) == 9:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            a = int(color[7:9], 16)
            return skia.Color(r, g, b, a)
        elif len(color) == 7:
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
            return default
    elif color in NAMED_COLORS:
        return parse_color(NAMED_COLORS[color])
    else:
        print("missing color", color)
        return default

def parse_blend_mode(blend_mode_str):
    match blend_mode_str:
        case "multiply":
            return skia.BlendMode.kMultiply
        case "difference":
            return skia.BlendMode.kDifference
        case "destination-in":
            return skia.BlendMode.kDstIn
        case "source-over":
            return skia.BlendMode.kSrcOver
        case _:
            return skia.BlendMode.kSrcOver

def get_font_linespace(font: skia.Font) -> int:
    metrics = font.getMetrics()
    return metrics.fDescent - metrics.fAscent

def paint_visual_effects(node, cmds, rect):
    opacity = float(node.style.get("opacity", "1.0"))
    blend_mode = node.style.get("mix-blend-mode")
    overflow = node.style.get("overflow", "visible")

    if overflow == "clip":
        if not blend_mode:
            blend_mode = "source-over"
        border_radius = float(
            node.style.get("border-radius", "0px")[:-2])
        cmds.append(Blend(1.0, "destination-in", [
            DrawRRect("white", border_radius,
                      x1=rect.x1, x2=rect.x2, y1=rect.y1, y2=rect.y2)
        ]))

    return [
        Blend(opacity, blend_mode, cmds),
    ]

def paint_tree(layout_object, display_list):
    cmds = []
    if layout_object.should_paint():
        cmds = layout_object.paint()
    for child in layout_object.children:
        paint_tree(child, cmds)
    
    if layout_object.should_paint():
        cmds = layout_object.paint_effects(cmds)
    display_list.extend(cmds)

@dataclass
class DrawObject:
    x1: int = field(kw_only=True, default=None)
    x2: int = field(kw_only=True, default=None)
    y1: int = field(kw_only=True, default=None)
    y2: int = field(kw_only=True, default=None)
    rect: skia.Rect = field(init=False)

    def __post_init__(self):
        self.rect = skia.Rect.MakeLTRB(self.x1, self.y1, self.x2, self.y2)


@dataclass
class DrawOutline(DrawObject):
    color: str
    thickness: int

    def execute(self, canvas):
        paint = skia.Paint(
            Color=parse_color(self.color),
            StrokeWidth=self.thickness,
            Style=skia.Paint.kStroke_Style,
        )
        canvas.drawRect(self.rect, paint)


@dataclass
class DrawLine(DrawObject):
    color: str
    thickness: int

    def execute(self, canvas):
        # this doesn't look right from the book, shouldn't scroll adjust y?
        path = (
            skia.Path()
            .moveTo(self.x1, self.y1)
            .lineTo(self.x2, self.y2)
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

    def execute(self, canvas):
        canvas.drawImage(self.image, self.x1, self.y1)


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

    def execute(self, canvas):
        paint = skia.Paint(
            AntiAlias=True,
            Color=parse_color(self.color),
        )
        baseline = self.y1 - self.font.getMetrics().fAscent
        canvas.drawString(self.text, float(self.x1), baseline, self.font, paint)


@dataclass()
class DrawRect(DrawObject):
    color: str

    def execute(self, canvas):
        paint = skia.Paint(Color=parse_color(self.color))
        canvas.drawRect(self.rect, paint)


@dataclass()
class DrawRRect(DrawObject):
    color: str
    radius: int
    rrect: skia.RRect = field(init=False)

    def __post_init__(self):
        super().__post_init__()
        self.rrect = skia.RRect.MakeRectXY(self.rect, self.radius, self.radius)

    def execute(self, canvas):
        paint = skia.Paint(Color=parse_color(self.color))
        canvas.drawRRect(self.rrect, paint)

@dataclass()
class Blend:
    opacity: int
    blend_mode: str 
    children: list[DrawObject]

    def __post_init__(self):
        self.rect = skia.Rect.MakeEmpty()
        self.should_save = self.opacity < 1 or self.blend_mode
        for cmd in self.children:
            self.rect.join(cmd.rect)
    
    def execute(self, canvas):
        # avoid creating unnecessary layers
        if self.should_save:
            paint = skia.Paint(
                Alphaf=self.opacity,
                BlendMode=parse_blend_mode(self.blend_mode))
            canvas.saveLayer(None, paint)
        for cmd in self.children:
            cmd.execute(canvas)
        if self.should_save:
            canvas.restore()