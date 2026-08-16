import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/renderWithProviders';
import { Select } from '../Select';

const OPTIONS = [
  { value: 'ALL', label: 'All engagements' },
  { value: 'e-1', label: 'Engagement One' },
  { value: 'e-2', label: 'Engagement Two' },
];

describe('Select', () => {
  it('renders a native combobox with its options', () => {
    renderWithProviders(
      <Select aria-label="Engagement" value="ALL" onChange={() => {}} options={OPTIONS} />,
    );

    const select = screen.getByRole('combobox', { name: 'Engagement' });
    expect(select).toBeInTheDocument();
    expect(screen.getAllByRole('option')).toHaveLength(3);
  });

  it('reports the chosen value', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn<() => void>();
    renderWithProviders(
      <Select aria-label="Engagement" value="ALL" onChange={onChange} options={OPTIONS} />,
    );

    await user.selectOptions(screen.getByRole('combobox', { name: 'Engagement' }), 'e-2');
    expect(onChange).toHaveBeenCalled();
  });

  it('keeps the product-wide focus ring instead of suppressing the outline', () => {
    renderWithProviders(
      <Select aria-label="Engagement" value="ALL" onChange={() => {}} options={OPTIONS} />,
    );

    // The copied original set `outline-none`, which left a border-color
    // change as the only focus indicator.
    expect(screen.getByRole('combobox', { name: 'Engagement' }).className).not.toContain(
      'outline-none',
    );
  });

  it('honours a disabled option', () => {
    renderWithProviders(
      <Select
        aria-label="Engagement"
        value="ALL"
        onChange={() => {}}
        options={[...OPTIONS, { value: 'e-3', label: 'Engagement Three', disabled: true }]}
      />,
    );

    expect(screen.getByRole('option', { name: 'Engagement Three' })).toBeDisabled();
  });
});
