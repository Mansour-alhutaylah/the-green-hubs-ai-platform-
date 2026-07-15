import { Badge } from '../Badge/Badge';
import { DiamondGlyph } from '../DiamondGlyph/DiamondGlyph';

export function DemoDataBadge({ label = 'Sample data · Demo workspace' }: { label?: string }) {
  return (
    <Badge className="border-leaf-300 bg-leaf-100 text-leaf-700">
      <DiamondGlyph variant="filled" size={7} />
      {label}
    </Badge>
  );
}
