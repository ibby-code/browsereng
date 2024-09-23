from dataclasses import dataclass, field
from PIL import ImageTk


@dataclass
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    def containsPoint(self, x, y):
        return x >= self.left and x < self.right and y >= self.top and y < self.bottom


@dataclass
class DrawOutline:
    rect: Rect
    color: str
    thickness: int

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.rect.left,
            self.rect.top - scroll,
            self.rect.right,
            self.rect.bottom - scroll,
            width=self.thickness,
            outline=self.color,
        )


@dataclass
class DrawLine:
    rect: Rect
    color: str
    thickness: int

    def execute(self, scroll, canvas):
        canvas.create_line(
            self.rect.left,
            self.rect.top - scroll,
            self.rect.right,
            self.rect.bottom - scroll,
            width=self.thickness,
            fill=self.color,
        )


@dataclass
class DrawImage:
    left: int
    top: int
    image: ImageTk.PhotoImage
    tags: list[str] = field(kw_only=True, default_factory=list)

    def execute(self, scroll, canvas, tags=[]):
        tags.extend(self.tags)
        canvas.create_image(
            self.left, self.top - scroll, anchor="nw", image=self.image, tags=tags
        )


@dataclass()
class DrawText:
    left: int
    top: int
    text: str
    font: "tkinter.font.Font"
    color: str
    bottom: int = field(init=False)
    rect: Rect = field(init=False)
    tags: list[str] = field(kw_only=True, default_factory=list)

    def __post_init__(self):
        self.bottom = self.top + self.font.metrics("linespace")
        self.rect = Rect(
            self.left, self.top, self.left + self.font.measure(self.text), self.bottom
        )

    def execute(self, scroll, canvas, tags=[]):
        tags.extend(self.tags)
        canvas.create_text(
            self.left,
            self.top - scroll,
            text=self.text,
            font=self.font,
            fill=self.color,
            anchor="nw",
            tags=tags,
        )


@dataclass()
class DrawRect:
    rect: Rect
    color: str
    tags: list[str] = field(kw_only=True, default_factory=list)

    def execute(self, scroll, canvas, tags=[]):
        tags.extend(self.tags)
        canvas.create_rectangle(
            self.rect.left,
            self.rect.top - scroll,
            self.rect.right,
            self.rect.bottom - scroll,
            width=0,
            fill=self.color,
            tags=tags,
        )
