import svgwrite


SCALE = 16
COLORS = [None, '#f00', '#0f0', '#00f']


def _rounded(x, y, w, h, r, **kwargs):
    path = svgwrite.path.Path(**kwargs)
    path.push(('M', x + r, y))
    path.push(('h', w - r - r))
    path.push(('a', r, r, 0, 0, 1, r, r))
    path.push(('v', h - r - r))
    path.push(('a', r, r, 0, 0, 1, -r, r))
    path.push(('h', -(w - r - r)))
    path.push(('a', r, r, 0, 0, 1, -r, -r))
    path.push(('v', -(h - r - r)))
    path.push(('a', r, r, 0, 0, 1, r, -r))
    path.push('Z')
    return path


def to_svg(modules, background=False):
    size = int(len(modules) ** 0.5)
    if size < 1 or len(modules) != size * size:
        raise ValueError('Invalid data')

    width = size + 10
    svg = svgwrite.Drawing(size=(width * SCALE, width * SCALE))

    symbols = []
    for i, color in enumerate(COLORS):
        if color is None:
            symbols.append(None)
            continue
        id = 'm' + str(i)
        symbol = svg.symbol(id=id)
        symbol.viewbox(0, 0, 1, 1)
        symbol.add(_rounded(0 + 1 / 16, 0 + 1 / 16, 1 - 2 / 16, 1 - 2 / 16, 4 / 16, fill=color))
        svg.defs.add(symbol)
        symbols.append(symbol)

    g = svgwrite.container.Group()
    g.scale(SCALE)
    if background:
        g.add(svgwrite.shapes.Rect(size=(width, width), fill='#fff'))
    g.add(_rounded(2, 2, size + 6, size + 6, 1, fill='#000'))
    g.add(_rounded(4, 4, size + 2, size + 2, 0.5, fill='#fff'))
    for x in range(size):
        for y in range(size):
            symbol = symbols[modules[x * size + y]]
            if not symbol:
                continue
            g.add(svg.use(symbol, insert=(x + 5, y + 5), size=(1, 1)))
    svg.add(g)

    return svg.tostring()
