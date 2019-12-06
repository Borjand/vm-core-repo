"""
shape input dialog
"""
import tkinter as tk
from tkinter import colorchooser, font, ttk

from coretk.dialogs.dialog import Dialog
from coretk.images import ImageEnum

FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]
BORDER_WIDTH = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class ShapeDialog(Dialog):
    def __init__(self, master, app, shape):
        self.annotation_type = app.canvas.annotation_type
        self.canvas = app.canvas
        if self.is_shape():
            super().__init__(master, app, "Add a new shape", modal=True)
            self.id = shape.id
            self.fill = None
            self.border = None
        else:
            super().__init__(master, app, "Add a new text", modal=True)

        self.shape = shape
        data = shape.shape_data
        self.shape_text = tk.StringVar(value=data.text)
        self.font = tk.StringVar(value=data.font)
        self.font_size = tk.IntVar(value=data.font_size)
        self.text_color = data.text_color
        self.fill_color = data.fill_color
        self.border_color = data.border_color
        self.border_width = tk.IntVar(value=data.border_width)
        self.bold = tk.IntVar(value=data.bold)
        self.italic = tk.IntVar(value=data.italic)
        self.underline = tk.IntVar(value=data.underline)
        self.top.columnconfigure(0, weight=1)
        self.draw()

    def is_shape(self):
        return (
            self.annotation_type == ImageEnum.OVAL
            or self.annotation_type == ImageEnum.RECTANGLE
        )

    def is_text(self):
        return self.annotation_type == ImageEnum.TEXT

    def draw(self):
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=2)
        label = ttk.Label(frame, text="Text for top of shape: ")
        label.grid(row=0, column=0, sticky="nsew")
        entry = ttk.Entry(frame, textvariable=self.shape_text)
        entry.grid(row=0, column=1, sticky="nsew")
        frame.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        combobox = ttk.Combobox(
            frame,
            textvariable=self.font,
            values=sorted(font.families()),
            state="readonly",
        )
        combobox.grid(row=0, column=0, sticky="nsew")
        combobox = ttk.Combobox(
            frame, textvariable=self.font_size, values=FONT_SIZES, state="readonly"
        )
        combobox.grid(row=0, column=1, padx=3, sticky="nsew")
        button = ttk.Button(frame, text="Text color", command=self.choose_text_color)
        button.grid(row=0, column=2, sticky="nsew")
        frame.grid(row=1, column=0, sticky="nsew", padx=3, pady=3)

        frame = ttk.Frame(self.top)
        button = ttk.Checkbutton(frame, variable=self.bold, text="Bold")
        button.grid(row=0, column=0)
        button = ttk.Checkbutton(frame, variable=self.italic, text="Italic")
        button.grid(row=0, column=1, padx=3)
        button = ttk.Checkbutton(frame, variable=self.underline, text="Underline")
        button.grid(row=0, column=2)
        frame.grid(row=2, column=0, sticky="nsew", padx=3, pady=3)

        if self.is_shape():
            frame = ttk.Frame(self.top)
            frame.columnconfigure(0, weight=1)
            frame.columnconfigure(1, weight=1)
            frame.columnconfigure(2, weight=1)
            label = ttk.Label(frame, text="Fill color")
            label.grid(row=0, column=0, sticky="nsew")
            self.fill = ttk.Label(
                frame, text=self.fill_color, background=self.fill_color
            )
            self.fill.grid(row=0, column=1, sticky="nsew", padx=3)
            button = ttk.Button(frame, text="Color", command=self.choose_fill_color)
            button.grid(row=0, column=2, sticky="nsew")
            frame.grid(row=3, column=0, sticky="nsew", padx=3, pady=3)

            frame = ttk.Frame(self.top)
            frame.columnconfigure(0, weight=1)
            frame.columnconfigure(1, weight=1)
            frame.columnconfigure(2, weight=1)
            label = ttk.Label(frame, text="Border color:")
            label.grid(row=0, column=0, sticky="nsew")
            self.border = ttk.Label(
                frame, text=self.border_color, background=self.fill_color
            )
            self.border.grid(row=0, column=1, sticky="nsew", padx=3)
            button = ttk.Button(frame, text="Color", command=self.choose_border_color)
            button.grid(row=0, column=2, sticky="nsew")
            frame.grid(row=4, column=0, sticky="nsew", padx=3, pady=3)

            frame = ttk.Frame(self.top)
            frame.columnconfigure(0, weight=1)
            frame.columnconfigure(1, weight=2)
            label = ttk.Label(frame, text="Border width:")
            label.grid(row=0, column=0, sticky="nsew")
            combobox = ttk.Combobox(
                frame,
                textvariable=self.border_width,
                values=BORDER_WIDTH,
                state="readonly",
            )
            combobox.grid(row=0, column=1, sticky="nsew")
            frame.grid(row=5, column=0, sticky="nsew", padx=3, pady=3)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        button = ttk.Button(frame, text="Add shape", command=self.click_add)
        button.grid(row=0, column=0, sticky="e", padx=3)
        button = ttk.Button(frame, text="Cancel", command=self.cancel)
        button.grid(row=0, column=1, sticky="w", pady=3)
        frame.grid(row=6, column=0, sticky="nsew", padx=3, pady=3)

    def choose_text_color(self):
        color = colorchooser.askcolor(color="black")
        self.text_color = color[1]

    def choose_fill_color(self):
        color = colorchooser.askcolor(color=self.fill_color)
        self.fill_color = color[1]
        self.fill.config(background=color[1], text=color[1])

    def choose_border_color(self):
        color = colorchooser.askcolor(color="black")
        self.border_color = color[1]
        self.border.config(background=color[1], text=color[1])

    def cancel(self):
        if self.is_shape() and not self.canvas.shapes[self.id].created:
            self.canvas.delete(self.id)
            self.canvas.shapes.pop(self.id)
        self.destroy()

    def click_add(self):
        if self.is_shape():
            self.add_shape()
        elif self.is_text():
            self.add_text()
        self.destroy()

    def make_font(self):
        """
        create font for text or shape label
        :return: list(font specifications)
        """
        size = int(self.font_size.get())
        text_font = [self.font.get(), size]
        if self.bold.get() == 1:
            text_font.append("bold")
        if self.italic.get() == 1:
            text_font.append("italic")
        if self.underline.get() == 1:
            text_font.append("underline")
        return text_font

    def save_text(self):
        """
        save info related to text or shape label

        :return: nothing
        """
        data = self.shape.shape_data
        data.text = self.shape_text.get()
        data.font = self.font.get()
        data.font_size = int(self.font_size.get())
        data.text_color = self.text_color
        data.bold = self.bold.get()
        data.italic = self.italic.get()
        data.underline = self.underline.get()

    def save_shape(self):
        """
        save info related to shape

        :return: nothing
        """
        data = self.shape.shape_data
        data.fill_color = self.fill_color
        data.border_color = self.border_color
        data.border_width = int(self.border_width.get())

    def add_text(self):
        """
        add text to canvas

        :return: nothing
        """
        text = self.shape_text.get()
        x = self.shape.x0
        y = self.shape.y0
        text_font = self.make_font()
        if self.shape.text_id is None:
            tid = self.canvas.create_text(
                x, y, text=text, fill=self.text_color, font=text_font, tags="text"
            )
            self.shape.text_id = tid
            self.id = tid
            self.shape.id = tid
            self.canvas.texts[tid] = self.shape
            self.shape.created = True
        self.save_text()
        print(self.canvas.texts)
        #     self.canvas.shapes[self.id].created = True
        # else:
        #     self.canvas.itemconfig(
        #         self.shape.text_id, text=text, fill=self.text_color, font=f
        #     )

    def add_shape(self):
        self.canvas.itemconfig(
            self.id,
            fill=self.fill_color,
            dash="",
            outline=self.border_color,
            width=int(self.border_width.get()),
        )
        shape_text = self.shape_text.get()
        size = int(self.font_size.get())
        x0, y0, x1, y1 = self.canvas.bbox(self.id)
        _y = y0 + 1.5 * size
        _x = (x0 + x1) / 2
        text_font = self.make_font()
        if self.shape.text_id is None:
            self.shape.text_id = self.canvas.create_text(
                _x,
                _y,
                text=shape_text,
                fill=self.text_color,
                font=text_font,
                tags="shapetext",
            )
            self.shape.created = True
        else:
            self.canvas.itemconfig(
                self.shape.text_id,
                text=shape_text,
                fill=self.text_color,
                font=text_font,
            )
        self.save_text()
        self.save_shape()
