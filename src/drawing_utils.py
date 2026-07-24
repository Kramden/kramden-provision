import cairo


def draw_screen_outline_and_strokes(
    ctx,
    width,
    height,
    strokes,
    background_rgb=(0.1, 0.1, 0.1),
    outline_rgb=(0.85, 0.85, 0.85),
    stroke_rgb=(0.94, 0.33, 0.13),
):
    """Shared paint routine for the screen/touchscreen defect drawing canvas,
    its read-only preview thumbnail, and the tracking sheet PDF image.

    Colors default to a dark background matching the app's dark theme; the
    PDF embed (printed in greyscale) passes a light/dark-inverted set so it
    doesn't print as a solid dark block.

    Stroke points are normalized (0.0-1.0, relative to width/height) rather
    than absolute pixels. This canvas is drawn at several different sizes --
    the live resizable dialog, the small preview thumbnail, and the fixed-size
    PDF embed -- and normalized coordinates are what let a drawing made at
    one size line up correctly when redrawn at another.
    """
    ctx.set_source_rgb(*background_rgb)
    ctx.rectangle(0, 0, width, height)
    ctx.fill()

    margin = max(3, min(width, height) * 0.06)
    ctx.set_source_rgb(*outline_rgb)
    ctx.set_line_width(2)
    ctx.rectangle(margin, margin, width - margin * 2, height - margin * 2)
    ctx.stroke()

    ctx.set_source_rgb(*stroke_rgb)
    ctx.set_line_width(3)
    ctx.set_line_cap(cairo.LineCap.ROUND)
    ctx.set_line_join(cairo.LineJoin.ROUND)
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        ctx.move_to(stroke[0][0] * width, stroke[0][1] * height)
        for point in stroke[1:]:
            ctx.line_to(point[0] * width, point[1] * height)
        ctx.stroke()
