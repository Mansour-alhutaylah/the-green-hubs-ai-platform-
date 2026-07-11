import {
  Bell,
  BookOpen,
  Building2,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Eye,
  EyeOff,
  FileText,
  Folder,
  Globe,
  LayoutDashboard,
  Leaf,
  Lock,
  LogOut,
  Menu,
  MoreHorizontal,
  RadioTower,
  ScanSearch,
  Search,
  Settings,
  ShieldCheck,
  TriangleAlert,
  Upload,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react';

/**
 * Curated MVP icon set (§14.4 / Appendix F) — only the nav / context-bar /
 * auth subset that Phase 1's shell actually renders. The remaining ~15
 * icons in Appendix F's full inventory (facility, meter, drone, framework
 * custom glyphs, table row actions, etc.) belong to the business modules
 * that consume them and are deferred to later phases.
 *
 * `hub-diamond` is intentionally absent here — it renders as the brand's
 * own DiamondGlyph rather than a lucide icon (see Icon.tsx).
 */
export const ICON_REGISTRY = {
  dashboard: LayoutDashboard,
  reports: FileText,
  documents: Folder,
  upload: Upload,
  analysis: ScanSearch,
  carbon: Leaf,
  telemetry: RadioTower,
  organizations: Building2,
  users: Users,
  frameworks: BookOpen,
  audit: ShieldCheck,
  'shield-check': ShieldCheck,
  settings: Settings,
  bell: Bell,
  search: Search,
  globe: Globe,
  'chevron-down': ChevronDown,
  'chevron-right': ChevronRight,
  check: Check,
  x: X,
  'log-out': LogOut,
  menu: Menu,
  lock: Lock,
  eye: Eye,
  'eye-off': EyeOff,
  'more-horizontal': MoreHorizontal,
  'triangle-alert': TriangleAlert,
  'circle-alert': CircleAlert,
} satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof ICON_REGISTRY | 'hub-diamond';

/** Icons that encode direction and must flip in RTL (§3.3: "icons that
 * encode direction flip; icons that don't (documents, bell) do not"). */
export const MIRRORED_ICONS: ReadonlySet<IconName> = new Set(['chevron-right']);
