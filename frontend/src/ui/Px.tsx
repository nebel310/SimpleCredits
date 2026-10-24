// Пиксельные иконки: одна иконка — одно значение. Каждая рисуется одним path без швов.
const BITMAPS = {
  heart: ['.XX..XX.', 'XXXXXXXX', 'XXXXXXXX', 'XXXXXXXX', '.XXXXXX.', '..XXXX..', '...XX...'], // бренд/шансы в целом
  check: ['........', '......XX', '.....XX.', 'XX..XX..', '.XXXX...', '..XX....', '........'], // высокий шанс, готово
  up: ['...XX...', '..XXXX..', '.XXXXXX.', 'XX.XX.XX', '...XX...', '...XX...', '...XX...'], // средний шанс
  wait: ['XXXXXXXX', '.X....X.', '..XXXX..', '...XX...', '..X..X..', '.X....X.', 'XXXXXXXX'], // ожидание
  alert: ['...XX...', '...XX...', '...XX...', '...XX...', '........', '...XX...', '...XX...'], // внимание, стоп
  gem: ['...X...', '..XXX..', '.XXXXX.', 'XXXXXXX', '.XXXXX.', '..XXX..', '...X...'], // ИИ
  doc: ['XXXXXX.', 'X....XX', 'X.XX..X', 'X.....X', 'X.XXX.X', 'X.....X', 'XXXXXXX'], // документ
  lock: ['..XXX...', '.X...X..', '.X...X..', 'XXXXXXX.', 'XXX.XXX.', 'XXX.XXX.', 'XXXXXXX.'], // нет прав
} as const;

export type PxName = keyof typeof BITMAPS;

const cache = new Map<string, { d: string; w: number; h: number }>();

function pathOf(name: PxName) {
  const hit = cache.get(name);
  if (hit) return hit;
  const rows = BITMAPS[name];
  let d = '';
  rows.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      if (row[x] === 'X') {
        let e = x;
        while (e < row.length && row[e] === 'X') e++;
        d += `M${x} ${y}h${e - x}v1h-${e - x}z`;
        x = e;
      } else x++;
    }
  });
  const r = { d, w: rows[0].length, h: rows.length };
  cache.set(name, r);
  return r;
}

export function Px({ name, size = 24, color = 'currentColor', label }: { name: PxName; size?: number; color?: string; label?: string }) {
  const { d, w, h } = pathOf(name);
  return (
    <svg
      className="px"
      width={(size * w) / h}
      height={size}
      viewBox={`0 0 ${w} ${h}`}
      shapeRendering="crispEdges"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <path d={d} fill={color} />
    </svg>
  );
}
