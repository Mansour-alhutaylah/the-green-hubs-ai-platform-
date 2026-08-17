import { useState, type ReactElement } from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/renderWithProviders';
import { LocaleContext, type LocaleContextValue } from '@/lib/i18n/context';
import { en } from '@/lib/i18n/strings/en';
import { Tabs, TabPanel } from '../Tabs';
import { tabButtonId } from '../tabIds';

/**
 * Renders inside a right-to-left locale context.
 *
 * The MVP ships English only, so `LocaleProvider` fails closed to LTR and
 * cannot be driven into RTL by a stored preference. The RTL foundation
 * itself is preserved for a future Arabic phase, and this is how it stays
 * under test in the meantime: supply the context value directly, exactly
 * as a real second locale would.
 */
function renderWithRtlLocale(ui: ReactElement) {
  const value: LocaleContextValue = {
    locale: 'ar',
    dir: 'rtl',
    setLocale: () => {},
    toggleLocale: () => {},
    t: (key) => en[key],
  };
  return render(<LocaleContext.Provider value={value}>{ui}</LocaleContext.Provider>);
}

type Value = 'all' | 'open' | 'closed' | 'archived';

function Harness({ initial = 'all' as Value, disableClosed = false }) {
  const [value, setValue] = useState<Value>(initial);
  return (
    <>
      <Tabs<Value>
        id="status"
        panelId="status-panel"
        label="Status"
        value={value}
        onChange={setValue}
        items={[
          { value: 'all', label: 'All' },
          { value: 'open', label: 'Open' },
          { value: 'closed', label: 'Closed', disabled: disableClosed },
          { value: 'archived', label: 'Archived' },
        ]}
      />
      <TabPanel id="status-panel" tabsId="status" value={value}>
        <p>Showing {value}</p>
      </TabPanel>
    </>
  );
}

describe('Tabs', () => {
  it('exposes tablist / tab / tabpanel semantics wired together', () => {
    renderWithProviders(<Harness />);

    expect(screen.getByRole('tablist', { name: 'Status' })).toBeInTheDocument();
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(4);

    for (const tab of tabs) {
      expect(tab).toHaveAttribute('aria-controls', 'status-panel');
    }

    const panel = screen.getByRole('tabpanel');
    expect(panel).toHaveAttribute('id', 'status-panel');
    expect(panel).toHaveAttribute('aria-labelledby', tabButtonId('status', 'all'));
  });

  it('marks exactly one tab selected and moves selection on click', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);

    expect(screen.getByRole('tab', { name: 'All' })).toHaveAttribute('aria-selected', 'true');

    await user.click(screen.getByRole('tab', { name: 'Open' }));

    expect(screen.getByRole('tab', { name: 'Open' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'All' })).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByRole('tabpanel')).toHaveAttribute(
      'aria-labelledby',
      tabButtonId('status', 'open'),
    );
  });

  it('keeps the tab strip to a single tab stop via a roving tabindex', () => {
    renderWithProviders(<Harness />);

    expect(screen.getByRole('tab', { name: 'All' })).toHaveAttribute('tabindex', '0');
    expect(screen.getByRole('tab', { name: 'Open' })).toHaveAttribute('tabindex', '-1');
  });

  it('moves focus with arrow keys and wraps around', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);

    await user.tab();
    expect(screen.getByRole('tab', { name: 'All' })).toHaveFocus();

    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Open' })).toHaveFocus();

    await user.keyboard('{ArrowLeft}{ArrowLeft}');
    expect(screen.getByRole('tab', { name: 'Archived' })).toHaveFocus();
  });

  it('supports Home and End', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness initial="closed" />);

    await user.tab();
    await user.keyboard('{End}');
    expect(screen.getByRole('tab', { name: 'Archived' })).toHaveFocus();

    await user.keyboard('{Home}');
    expect(screen.getByRole('tab', { name: 'All' })).toHaveFocus();
  });

  it('activates the focused tab with Enter and Space, not on focus alone', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);

    await user.tab();
    await user.keyboard('{ArrowRight}');
    // Manual activation: focus has moved, selection has not.
    expect(screen.getByRole('tab', { name: 'All' })).toHaveAttribute('aria-selected', 'true');

    await user.keyboard('{Enter}');
    expect(screen.getByRole('tab', { name: 'Open' })).toHaveAttribute('aria-selected', 'true');

    await user.keyboard('{ArrowRight}');
    await user.keyboard(' ');
    expect(screen.getByRole('tab', { name: 'Closed' })).toHaveAttribute('aria-selected', 'true');
  });

  it('skips a disabled tab when navigating and refuses to select it', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness disableClosed />);

    await user.tab();
    await user.keyboard('{ArrowRight}{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Archived' })).toHaveFocus();

    await user.click(screen.getByRole('tab', { name: 'Closed' }));
    expect(screen.getByRole('tab', { name: 'Closed' })).toHaveAttribute('aria-selected', 'false');
  });

  /* The MVP ships English only, so `LocaleProvider` can no longer be driven
     into RTL through a stored preference. The primitive's RTL behaviour is
     part of the preserved right-to-left foundation, so it is exercised by
     supplying an RTL locale context directly — which is what a future
     Arabic phase will do for real. */
  it('reverses the arrow directions in RTL', async () => {
    const user = userEvent.setup();
    renderWithRtlLocale(<Harness />);

    await user.tab();
    // Laid out right-to-left, ArrowLeft moves to the next tab.
    await user.keyboard('{ArrowLeft}');
    expect(screen.getByRole('tab', { name: 'Open' })).toHaveFocus();

    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'All' })).toHaveFocus();
  });
});
