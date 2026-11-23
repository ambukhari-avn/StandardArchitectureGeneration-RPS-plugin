"""Place editable cable labels beside orthogonal paths, clear of devices and crossings."""
from textfit import fit_size

TYPICAL_LABEL = 'Typical Hardwired Signals \u2014 AI/DI/AO/DO'
GROUPED_NOTE = 'Grouped hardwired lines represent multiple physical field connections; individual instrument-to-I/O relationships are retained in the architecture data.'


def draw(page, lines, paths, shapes, warnings, B):
    blocked = [B.rect_of(s) for s in shapes if s['kind'] not in B.SEE_THROUGH]
    blocked += [(s['x'], s['y'], s['w'], s['h']) for s in page.shapes
                if s['kind'] == 'text' and s['text']]
    def overlaps(a, b):
        return a[0] < b[0]+b[2]+.03 and a[0]+a[2] > b[0]-.03 and a[1] < b[1]+b[3]+.03 and a[1]+a[3] > b[1]-.03
    for index, (line, pts) in enumerate(zip(lines, paths)):
        label = line.get('label')
        if not label:
            continue
        w, h = min(3.1, max(1.5, len(label) * .049)), .24
        candidates = []
        for a, b in sorted(zip(pts, pts[1:]), key=lambda pair: -abs(pair[0][0]-pair[1][0])-abs(pair[0][1]-pair[1][1])):
            for t in (.5, .25, .75):
                x, y = a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t
                if abs(a[1]-b[1]) < 1e-6:
                    candidates += [(x-w/2, y+.07, w, h), (x-w/2, y-h-.07, w, h)]
                else:
                    candidates += [(x+.09, y-h/2, w, h), (x-w-.09, y-h/2, w, h)]
        rect = next((r for r in candidates if r[0] >= B.MARGIN and r[0]+w <= B.MARGIN+B.AREA_W
                     and r[1] >= B.BOTTOM and r[1]+h <= B.TOP
                     and not any(overlaps(r, other) for other in blocked)
                     and not any(B.crosses(path, r, inset=0) for path in paths)), None)
        if rect is None:
            raise B.BuildError('Cable label cannot fit clear of equipment and intersections: %s; increase spacing or adjust the route' % label)
        size = fit_size(label, w, h, (7, 6.5, 6))
        page.text(*rect, label, size=size, key='cable-label:%s->%s:%d' % (line['a'], line['b'], index))
        blocked.append(rect)
