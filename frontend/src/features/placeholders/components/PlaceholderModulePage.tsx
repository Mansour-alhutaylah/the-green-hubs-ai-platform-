import type { IconName } from '@/design-system';
import { ComingSoonPage } from './ComingSoonPage';

export interface PlaceholderModulePageProps {
  title: string;
  /** The module's own Command Rail icon — ties the placeholder visually
   * back to the nav item that links here, instead of a generic glyph. */
  icon: IconName;
  /** One sentence: what the module will do. */
  description: string;
  /** One sentence: what unlocks it. */
  unlock: string;
}

/**
 * §11.8 future-module placeholder pattern: real chrome (a PageHeader, same
 * as any shipped module) with the content zone as a quiet, bordered notice
 * — never a marketing splash, never a tiled/checkerboard texture, never a
 * stock illustration. The one available action ("Notify me when available")
 * writes a notification preference; Phase 1 stands that up as a toast
 * confirmation since the Notifications module itself is a later phase's
 * business logic.
 */
export function PlaceholderModulePage({
  title,
  icon,
  description,
  unlock,
}: PlaceholderModulePageProps) {
  return <ComingSoonPage title={title} icon={icon} description={description} unlock={unlock} />;
}
