import { Button, DiamondGlyph, Icon } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { AuthPageHeader } from './AuthPageHeader';

export interface PreviewWorkspaceEntryProps {
  onEnter: () => void;
  isSubmitting: boolean;
  error?: string;
}

/**
 * The entire sign-in surface of a Preview build.
 *
 * There is no email field, no password field, and no credential submission
 * — which is the point. A Preview build must not be able to fall through to
 * real authentication, and the most reliable way to guarantee that is to
 * not render a credential form at all. Entering the workspace mints a local
 * synthetic session and makes no network request of any kind.
 *
 * This component only ever mounts when the active `AuthService` exposes
 * `enterPreviewWorkspace`, which only the Preview service does.
 */
export function PreviewWorkspaceEntry({
  onEnter,
  isSubmitting,
  error,
}: PreviewWorkspaceEntryProps) {
  const { t } = useLocale();

  return (
    <div>
      <div
        className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl border border-leaf-300 bg-leaf-100 text-leaf-700 shadow-card"
        aria-hidden
      >
        <Icon name="eye" size={22} />
      </div>
      <AuthPageHeader
        eyebrow={t('preview.ribbon.label')}
        heading={t('auth.preview.title')}
        supporting={t('auth.preview.supporting')}
        spacing="compact"
      />

      <div className="rounded-l border border-leaf-300 bg-mist-50 p-3 sm:p-4">
        <p className="flex items-start gap-2 text-meta leading-6 text-gray-600">
          <DiamondGlyph variant="hollow" size={10} className="mt-1.5 shrink-0 text-leaf-700" />
          <span>{t('auth.preview.notice')}</span>
        </p>
      </div>

      <Button
        type="button"
        size="xl"
        className="mt-4 w-full"
        isLoading={isSubmitting}
        onClick={onEnter}
      >
        {t('auth.preview.enter')}
      </Button>

      {error && (
        <p className="mt-3 text-meta text-amber-700" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
